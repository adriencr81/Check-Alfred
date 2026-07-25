# 0024 — Disponibilité de l'auditeur : quarantaine et empreinte de contenu

**Date** : 2026-07-25 · **Statut** : Accepté · **Signé** : Adrien (« ok lot 2 »),
Claude Code (pentest + conception)

## Contexte

Suite du pentest du 2026-07-25 (lot 2). L'ADR 0023 a fermé les contournements du
*mandat* ; restent les deux failles qui n'essaient pas de tromper Alfred mais de
**l'éteindre** — pour un agent adverse, c'est le chemin le plus court, et celui
qui ne laisse aucune déviation derrière lui.

1. **Un span malformé arrête la supervision, définitivement.**
   `trace/ingest.py::_timestamp` fait `int(nanos)` puis
   `datetime.fromtimestamp` : un `startTimeUnixNano` non numérique ou hors plage
   lève `ValueError`, que `ingest_otlp_json` ne convertit pas (il ne rattrape que
   `KeyError`/`TypeError`) et que `cli.py::_cmd_watch` ne rattrape pas non plus
   (il n'attend que `TraceIngestionError`/`OSError`). PoC : un fichier de trace de
   200 octets suffit à faire sortir `alfred watch` en 1 avec un traceback — et
   comme `watch_once` n'écrit `.alfred/seen.json` qu'après la boucle complète,
   **l'état ne progresse jamais** : chaque relance replante sur le même fichier.
   Dans le même dossier, un appel `wire_transfer` non autorisé n'a jamais été
   rapporté. En mode `--loop`, la supervision s'arrête tout court.
2. **`seen.json` n'indexe que des noms de fichiers.** `watch_once` filtre sur
   `p.name not in seen`. PoC : après une passe propre, l'agent réécrit
   `01-good.json` avec un appel `exfiltrate_database` → `alfred watch: no new
   trace files.` L'activité n'est jamais auditée.

Même classe de fragilité, même fichier : en `--loop`, une `DeliverError` (Slack
indisponible) ou une `NarrateError` remonte hors du `try` et tue la boucle. Un
incident chez un tiers éteint la supervision.

## Décisions

**1. Toute erreur de normalisation devient une `TraceIngestionError`.**
`_span_to_event` enveloppe `AttributeError`, `KeyError`, `OverflowError`,
`TypeError` et `ValueError` en nommant le `spanId` fautif. Le contrat d'ingestion
redevient « une seule famille d'erreurs typées », ce que la couche appelante
prétendait déjà rattraper.

**2. Un fichier illisible est mis en quarantaine, la passe continue.**
`watch_once` isole chaque fichier : celui qui échoue est enregistré comme
`quarantined` (avec sa raison) et les autres sont ingérés normalement. La passe
se termine, les digests des fichiers sains sont livrés. Alternative écartée :
échouer la passe entière — c'est le comportement actuel, et c'est précisément le
levier de déni de service.

**3. La quarantaine est rappelée à chaque passe, et `alfred watch` sort en 1
tant qu'elle dure.** `watch_once` renvoie *tous* les fichiers encore en
quarantaine, pas seulement ceux de la passe : un trou dans l'audit doit rester
visible dans les logs cron jusqu'à ce qu'un humain corrige ou supprime le
fichier. Les digests sont livrés quand même — la sortie 1 signale « audit
partiel », jamais « rien fait ». Alternative écartée : signaler une seule fois —
un cron quotidien oublierait le trou dès le lendemain.

**4. Un fichier est « déjà vu » sur son empreinte SHA-256, plus sur son nom.**
`.alfred/seen.json` passe en v2 : `{"version": 2, "files": {<nom>: {"sha256": …,
"status": …, "reason": …}}}`. Une réécriture (même nom, contenu différent) est
ré-ingérée — y compris pour un fichier en quarantaine, ce qui est la façon dont
un humain le débloque : il corrige le fichier, la passe suivante l'ingère.
Le coût est une lecture supplémentaire du fichier pour le hash, assumé : les
traces sont petites et la lecture est déjà le gros du travail.

**5. Migration v1 par adoption silencieuse.** Un `seen.json` v1 (liste de noms)
est relu tel quel ; à la première passe v2, chaque nom connu adopte l'empreinte
courante de son fichier **sans ré-ingestion**. Aucun digest en double à la mise à
jour ; en contrepartie, une réécriture antérieure à la mise à jour reste
invisible — le contrôle démarre maintenant. Un nom sans fichier présent est
conservé sans empreinte, donc un futur fichier portant ce nom sera ingéré
(fail-closed). Alternative écartée : tout ré-ingérer une fois — vérifie l'état de
départ, au prix d'une rafale de digests en double vers Slack.

**6. L'état est persisté après chaque fichier.** `_save_state` est appelé une fois
le fichier traité (ingéré *ou* mis en quarantaine), et seulement après que
`store.put_many` a réussi : une interruption (Ctrl-C, OOM, coupure) ne perd plus
la passe, et un échec du store laisse le fichier à re-traiter.

**7. La boucle survit à une panne de livraison.** En `--loop`, `DeliverError` et
`NarrateError` sont imprimées sur stderr et la passe suivante a lieu. En passe
simple, le fail-loud actuel est conservé (sortie 1) : là, c'est l'appelant — cron —
qui décide de réessayer.

## Règle produit (D5) — non violée

Rien de ce lot ne fabrique une affirmation : la quarantaine *retire* du contenu
non vérifiable et le dit. Un fichier en quarantaine ne produit aucune ligne de
digest, aucune déviation (il n'a pas d'`event_id` à citer) — il produit un
avertissement hors digest, ce qui est exactement la position honnête.

## Limites assumées

- **Un agent qui n'écrit aucune trace reste invisible.** Alfred audite ce qui est
  émis ; l'absence de trace n'est pas détectable depuis la trace. Détecter un
  silence anormal demanderait un attendu déclaré (« cet agent doit produire au
  moins N tâches/jour »), hors périmètre v0.x.
- **Suppression de fichier.** Effacer un fichier de trace déjà ingéré ne retire
  rien du store (les events y sont), mais efface la preuve d'origine ; l'ADR 0001
  et le lot 4 (écrasement par `INSERT OR REPLACE`) traitent la partie stockage.
- **La quarantaine mémorise un nom.** Deux fichiers différents portant
  successivement le même nom partagent une entrée ; c'est l'empreinte qui
  tranche, donc le comportement reste correct, mais l'historique n'est pas
  conservé (une seule entrée par nom).

## Conséquences

- `src/alfred/trace/ingest.py` : erreurs typées (décision 1).
- `src/alfred/watch.py` : `WatchPass`/`QuarantinedTrace`, état v2 avec empreinte,
  persistance par fichier, migration v1.
- `src/alfred/cli.py` : rapport de quarantaine + code de sortie, boucle qui
  survit à une panne de livraison.
- Tests falsifiables : `tests/test_trace_ingest.py`, `tests/test_watch.py`,
  `tests/test_cli.py`.
- Docs : CHANGELOG, `docs/integrate.md` (contrat de `alfred watch`).
- DoD inchangée : `pytest -q`, `ruff check .`, `mypy --strict src/` verts.

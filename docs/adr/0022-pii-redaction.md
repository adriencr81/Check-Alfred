# 0022 — Redaction PII/secrets déclarative à l'ingestion

**Date** : 2026-07-24 · **Statut** : Accepté · **Signé** : Adrien (demande
produit « attaque la redaction PII »), Claude Code (audit + conception)

## Contexte

Audit du 2026-07-24, en préparation d'un usage par de vrais clients (dont les
secteurs cibles assurance/finance/santé, PLAN.md §7). État constaté :

1. **PII au repos.** `alfred.trace.store` persiste le dict `attributes` complet
   en JSON clair dans SQLite (`_event_to_row` → `json.dumps`). Ce dict porte
   `tool.arguments.<clé>` — emails, noms, contenus de commande, potentiellement
   secrets/clés. La valeur brute des clients d'un déployeur se retrouve donc en
   clair sur son disque.
2. **PII en transit.** Ces mêmes valeurs ressortent dans les messages de
   déviation (`engine.py`), donc dans le digest Slack, le rapport HTML
   partageable (F4), et le digest envoyé à un LLM externe via `--narrate`.

PLAN.md §13 listait « redaction PII/secrets avant stockage/envoi » en **mention
honorable** (« à monter dans le top 5 si la priorité passe de l'adoption
communautaire aux secteurs régulés »). La priorité y passe : c'est un bloquant
dur avant tout démarchage régulé. Cet ADR la promeut au périmètre livré.

## Décisions

**1. Redaction à l'ingestion, avant le trace store — data minimization.** La
valeur brute est masquée au point d'ingestion (`alfred.trace.ingest`), donc
elle **n'entre jamais dans SQLite**. Un choke point unique couvre
mécaniquement toutes les sorties en aval (store, Slack, HTML, narration LLM) :
ce qui n'est jamais stocké ne peut pas fuir. Alternative écartée : redacter
seulement à la livraison — garderait la valeur brute au repos, garantie plus
faible pour les secteurs cibles.

**2. Liste explicite déclarée dans le mandat, pas de détection heuristique.**
Le mandat gagne un champ optionnel `redact: [<nom>, ...]`. Un attribut est
masqué si sa clé est dans la liste, ou si sa clé est `tool.arguments.<nom>`
pour un `<nom>` de la liste (couvre le nom court d'argument et une clé
d'attribut complète, p.ex. `gen_ai.prompt`). Déterministe, aucun faux
positif/négatif, fidèle à l'ADN « mandat déclaratif ». Alternative écartée :
détection par motifs (regex emails/cartes/clés) — heuristique, non
déterministe, peut sur-masquer ou rater ; contraire à « chaque chose est
calculée de façon déterministe ». Reste ouverte comme opt-in futur si la
demande émerge.

**3. Remplacement par un hash stable `redacted:sha256:<12hex>`.** La valeur
devient `redacted:sha256:` + les 12 premiers hex du SHA-256 de sa forme
chaîne. Le contenu est caché mais l'égalité/inégalité est préservée : deux
valeurs identiques donnent le même jeton, deux différentes des jetons
différents — donc `loop_detected` et la détection de répétition (qui comparent
les signatures d'arguments) restent corrects sur un champ masqué. Alternative
écartée : marqueur fixe unique — collapserait toutes les valeurs en une seule,
créant de faux `loop_detected`.

**4. Le moteur de mandat ne change pas de vocabulaire.** La redaction vit
entièrement dans la couche d'ingestion (garde-fou §9 du PLAN : couche
d'adaptation). `engine.py`, `report/build.py`, `deliver`, `narrate` sont
inchangés — ils voient simplement une valeur déjà masquée.

**5. Garde-fou anti-footgun au lint.** `alfred mandate lint` émet un WARNING si
une entrée `redact` coïncide avec l'`arg` d'une règle `forbidden_actions`
structurée : masquer un champ numérique de police le transforme en chaîne,
donc `_rule_matches` (qui ne déclenche que sur int/float) cesse silencieusement
de le contrôler. On alerte plutôt que laisser passer (« aucune supposition
silencieuse », CLAUDE.md).

## Règle produit (D5) — non violée

On masque une *valeur* d'attribut, jamais un event. Chaque `event_id` reste
présent et chaque ligne de rapport reste ancrée sur un event réel. Aucun résumé
auto-déclaré n'est introduit ; l'ancrage est intact.

## Limites assumées (à documenter)

- **Aveugle hors liste.** Seuls les champs déclarés sont masqués ; une PII dans
  un attribut non listé passe. C'est le prix du déterminisme (décision 2).
- ~~**Hash non salé.**~~ **Levée par l'ADR 0025 (décision 3).** Le compromis
  décrit ici — un hash devinable par dictionnaire pour une valeur à faible
  entropie — n'a pas tenu au pentest. Le masque est désormais un HMAC-SHA256
  sous une clé par projet (`.alfred/redaction-key`), ce qui préserve l'égalité
  intra-projet dont dépend `loop_detected` sans laisser la valeur se retrouver.
  La décision 3 ci-dessus est amendée en conséquence (forme du jeton :
  `redacted:hmac:<12 hex>`).
- **Champs de police.** Redacter un argument utilisé par une règle numérique
  désactive cette règle (décision 5 alerte, ne bloque pas — c'est un choix du
  déployeur).

## Conséquences

- Nouveau fichier : `src/alfred/trace/redact.py` (cœur pur, zéro dépendance).
- `src/alfred/trace/ingest.py` : `ingest_otlp_json`/`ingest_otlp_file` gagnent
  un param optionnel `redact=frozenset()`, appliqué en post-passe. Rétro-
  compatible : tout appel existant garde le défaut vide.
- `src/alfred/mandate/model.py` : `Mandate` gagne `redact: frozenset[str]`.
- `src/alfred/mandate/yaml_io.py` : parse/dump du champ `redact`.
- `src/alfred/watch.py`, `src/alfred/cli.py` : `alfred watch` et `alfred report`
  passent `mandate.redact` à l'ingestion.
- `src/alfred/mandate/lint.py` : WARNING de shadowing (décision 5).
- Tests falsifiables : `tests/test_trace_redact.py` (dont le test « jamais dans
  le store »), ajouts à `test_mandate_yaml.py` et `test_mandate_lint.py`.
- Docs : section « Redacting PII » dans `docs/integrate.md`, mention README,
  exemple commenté dans `examples/mandates/refund-bot.yaml`, entrée CHANGELOG.
- PLAN.md §13 : note de révision (feature promue de mention honorable, cet ADR).
- Exigences §5 inchangées (`pytest -q`, `ruff check .`, `mypy --strict src/`
  verts à la DoD).

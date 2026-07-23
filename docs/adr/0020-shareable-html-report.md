# 0020 — Rapport HTML statique partageable

**Date** : 2026-07-23 · **Statut** : Accepté · **Complète** : ADR 0005 (Brique 3), ADR 0012 (sinks), PLAN.md §13 F4

## Contexte

Le digest Alfred vit dans stdout et Slack — **éphémère**. Un manager qui veut
*forwarder* la preuve navigable (à sa hiérarchie, à un audit) n'a rien à
transmettre. F4 (PLAN.md §13, ligne 676) livre un **fichier HTML autonome** :
`alfred report --html`, chaque ligne du rapport cliquable vers ses events source,
dans le même fichier. Contraintes du backlog : lecture seule, **zéro infra** (un
fichier généré, pas de dashboard §10), **délibérément plus pauvre** que l'export
« dossier de preuve » payant (v0.4) pour ne pas le cannibaliser.

Contrainte absolue (CLAUDE.md) : chaque affirmation reste calculée depuis un
`event_id` de trace. L'HTML n'est **qu'un rendu de plus** du `Digest` existant —
même donnée que stdout/Slack, exactement le même ancrage. Le renderer ne calcule
rien : il met en page un `Digest` déjà construit.

## Décisions

**1. L'HTML est un troisième renderer du `Digest`, pas une nouvelle donnée.**
`report.html.render_html(digest) -> str`, à côté de `report.render.render` (texte)
et `deliver.slack.build_block_kit_payload` (Block Kit). Il **réutilise** `LABELS`,
`format_value` et `format_baseline` de `report.render` — labels, valeurs et
baselines (F3, ⚠️ inclus) restent identiques entre tous les sinks (même discipline
que le sink Slack, cf. docstring de `render`).

**2. Un fichier autonome, zéro JavaScript.** Document HTML5 complet : `<!doctype
html>`, CSS **inline** dans `<style>`, aucune ressource externe (pas de `<script>`,
pas de `src=`, pas de CDN/police/`http`). La navigation « ligne → event source »
se fait par **ancres `#evt-n`** pures — cohérent « zéro infra » : le fichier
s'ouvre hors ligne, se forwarde tel quel, ne dépend de rien.

**3. Ancrage indexé, pas l'`event_id` brut.** On collecte les `event_id` distincts
(lignes puis déviations, ordre de première apparition) → une map `event_id →
"evt-<n>"`. Chaque source est rendue `<a href="#evt-n">{event_id}</a>` ; la section
**Evidence** liste chaque `event_id` distinct avec `id="evt-n"`. Le lien et sa
cible venant de la **même map**, tout `#evt-n` résout — l'indice contourne tout
souci d'échappement ou de collision de fragment que poserait un `event_id`
arbitraire en `id`. C'est le comportement qui rend « chaque ligne cliquable vers
ses events source » littéralement vrai dans un seul fichier.

**4. Evidence = `event_id` seul, délibérément plus pauvre que le dossier payant.**
La section Evidence affiche l'`event_id` (entier — l'HTML n'a pas la contrainte de
largeur du rendu texte, donc pas de troncature `format_sources`), pas les
attributs de l'event. Fidèle au `Digest` (qui ne porte que des IDs) et clairement
en-deçà de l'export « dossier de preuve » (v0.4) qui, lui, déroulera les events.
Les `sources` historiques d'une baseline restent **non liées**, comme dans
stdout/Slack : ce rendu surface les ancres du jour, pas celles de la comparaison.

**5. Un fichier HTML par jour calendaire.** Miroir exact de `watch` (un `Digest`
par jour). `--out` est un **répertoire** (défaut : le répertoire courant),
fichiers nommés `alfred-<agent>-<date>.html` (agent slugifié). Aucun choix
silencieux d'un jour, multi-jours géré proprement (CLAUDE.md : pas de supposition
silencieuse).

**6. `report` re-génère à la demande, sans couplage `seen.json`.** Contrairement à
`watch` (qui saute les fichiers déjà vus pour ne pas ré-émettre un digest),
`report` ingère **tous** les `*.json` du dossier et re-rend à chaque appel — un
rapport partageable est fait pour être régénéré. Il réutilise le store configuré
(donc les baselines F3 depuis l'historique) via `put_many` (idempotent, `INSERT OR
REPLACE`), mais n'écrit ni ne lit `seen.json`.

**7. Réutilisation du pipeline, pas duplication.** Le cœur commun de `watch_once`
— grouper par jour + attacher la baseline — est extrait en
`watch.build_digests(mandate, events, store)`, appelé par `watch_once` **et**
`_cmd_report`. La boucle glob+ingest partagée entre `report` et `mandate init` est
factorisée en `cli._read_trace_events`. Comportement de `watch_once` inchangé
(tests existants garants).

**8. `--html` est un flag explicite (seul format aujourd'hui).** Son absence
renvoie une erreur guidée plutôt qu'un défaut deviné — laisse la porte ouverte à
un futur `--md`/`--json` sans supposer le format voulu (CLAUDE.md).

**9. Tout texte externe est échappé (`html.escape`).** Nom d'agent, message de
déviation, `event_id` : rien n'est injecté brut, un mandat ou une trace piégés ne
peuvent pas injecter de HTML.

## Conséquences

- `src/alfred/report/html.py` : `render_html`, `_anchor_map`, `_source_links`,
  `_line_row`, `_deviation_item`, constante `_STYLE` (CSS inline). Aucun état, une
  fonction pure `Digest -> str`.
- `src/alfred/watch.py` : extraction de `build_digests(mandate, events, store)` ;
  `watch_once` s'y ramène (comportement identique).
- `src/alfred/cli.py` : sous-commande `report` (`_cmd_report`), helpers `_slug` et
  `_read_trace_events` (partagé avec `mandate init`).
- Tests falsifiables : `tests/test_report_html.py` (document autonome sans
  ressource externe, labels/valeurs/baseline, **chaque lien source résout vers une
  ancre Evidence**, déviation ancrée, échappement anti-injection, ID long affiché
  entier, section déviations omise si clean) ; `tests/test_cli.py` (écriture du
  fichier `alfred-<agent>-<date>.html`, **re-génération idempotente** — falsifie
  tout couplage `seen.json`, `--html` requis, dossier vide, projet manquant).
- `README.md` : mention de l'export, ligne quickstart, sous-section « rapport
  HTML », note d'archi. `CHANGELOG.md` : entrée sous Unreleased. `PLAN.md §13` :
  F4 marquée livrée (ADR 0020). `pyproject.toml` **inchangé** (aucune dépendance —
  `html` est dans la stdlib).

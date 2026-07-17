# 0007 — Conception de la livraison Slack + CLI (Brique 5)

**Date** : 2026-07-17 · **Statut** : Accepté · **Signé** : Claude Code (Brique 5)

## Contexte

Le PLAN.md (§5, Brique 5) fixe l'objectif (webhook Slack Block Kit, commandes
`alfred init` + `alfred watch`) et les trois tests falsifiables, mais laisse
ouverts : le comportement exact de `watch` (passe unique ou démon), où
stocker l'état des fichiers déjà ingérés, la source du contenu du payload
Slack, et comment valider "le validator Block Kit officiel" alors que Slack
ne publie aucun schéma JSON téléchargeable. Deux points ont été tranchés
avec l'utilisateur avant implémentation (discipline CLAUDE.md : « ne pas
deviner, demander »), les autres ont été résolus par les recommandations
proposées faute de réponse structurée disponible côté outillage.

## Décisions

**1. `alfred watch` fait une passe unique, pas un démon.** Décision
utilisateur explicite. Chaque invocation scanne le dossier de traces une
fois, ingère les fichiers `*.json` non encore vus, produit et livre un
digest par jour calendaire trouvé, puis termine. Zéro thread, zéro
polling-loop : cohérent avec la philosophie « zéro infra » du produit
(`TraceStore` SQLite fichier unique) et bien plus simple à tester
(`tests/test_watch.py` n'a besoin d'aucun mock de temps ni de signal
d'arrêt). Se relance via cron si l'utilisateur veut un vrai « watch »
continu — hors scope v0.1.

**2. État des fichiers vus dans un fichier séparé, `.alfred/seen.json`.**
Décision utilisateur explicite. `.alfred/config.toml` (écrit une fois par
`alfred init`) reste purement déclaratif et n'est jamais réécrit par
`watch` ; l'état mutable (liste triée des noms de fichiers déjà ingérés)
vit dans `.alfred/seen.json`, lu/écrit par `alfred.watch._load_seen` /
`_save_seen`. Sépare la configuration utilisateur de l'état machine.

**3. Structure de fichiers — déviation documentée de PLAN.md §4.**
L'esquisse `deliver/{__init__.py, slack.py, stdout.py}` est suivie
telle quelle. Deux modules non prévus par l'esquisse sont ajoutés,
suivant la même discipline que l'ADR 0006 (séparer les types/logique
d'un besoin réel plutôt que suivre un plan de fichiers de haut niveau
non verrouillé) :
- `alfred/config.py` : scaffolding + lecture de `.alfred/config.toml`
  (`init_project`, `load_config`), nécessaire pour que `init` et `watch`
  partagent un seul point de vérité sur l'emplacement du mandat et du
  trace store.
- `alfred/watch.py` : la logique d'ingestion à passe unique
  (`watch_once`), séparée de `cli.py` pour rester testable sans passer
  par argparse — même pattern que `mandate.engine`/`report.build`
  découplés de toute préoccupation CLI.

**4. `alfred init` réutilise `alfred.mandate.yaml_io.dump_mandate`.**
Le mandat scaffoldé est un `Mandate` réel (agent fourni par
`--agent`, outils/interdictions/escalades vides, budget par défaut
5,00 €) sérialisé par la fonction existante — aucune duplication de la
logique YAML de la Brique 2. `init_project` refuse d'écraser un projet
existant (`mandate.yaml` ou `.alfred/config.toml` déjà présents lève
`ConfigError`) : pas d'écrasement silencieux, cohérent avec le principe
« fail loudly » déjà appliqué en Brique 4.

**5. Écriture TOML minimale faite à la main, aucune nouvelle
dépendance.** La lecture utilise `tomllib` (stdlib depuis Python 3.11).
Pour l'écriture, `.alfred/config.toml` ne porte que des clés `str` plates
(`mandate_path`, `trace_db_path`, `slack_webhook_url` optionnel) : les
chaînes basiques TOML partagent l'échappement JSON, donc
`alfred.config._dump_toml` sérialise chaque valeur avec `json.dumps` —
suffisant pour ce besoin fixe et documenté comme tel (pas un writer TOML
généraliste). Zéro dépendance ajoutée, conforme à CLAUDE.md.

**6. Payload Slack = digest rendu (Brique 3), pas la prose narrée
(Brique 4).** Le DoD de Brique 5 décrit explicitement le pipeline comme
« fixture trace → digest → payload Slack » (pas de `NarratedDigest`
mentionné), et le diagramme d'architecture (PLAN.md §3) montre
`report` → `deliver` et `report` → `narrate` comme deux branches
parallèles, pas `narrate` → `deliver`. `alfred.deliver.slack.
build_block_kit_payload` enveloppe donc directement le texte de
`alfred.report.render.render(digest)` (un bloc `header` avec le titre,
un bloc `section` `mrkdwn` avec le corps entier dans un bloc de code) —
une seule source de vérité pour la mise en forme du digest, pas de
logique de blocks dupliquée par ligne. Brancher `narrate` sur Slack reste
une extension future possible, hors scope v0.1.

**7. Validation Block Kit — fixture de contraintes maison, zéro nouvelle
dépendance.** Slack ne publie aucun JSON Schema officiel téléchargeable
pour Block Kit (uniquement de la doc et une validation côté serveur à
l'envoi réel). Plutôt que d'ajouter `jsonschema` pour valider contre un
schéma qui n'existe pas réellement côté Slack, `tests/fixtures/
block_kit_constraints.json` encode à la main les contraintes documentées
pour les seuls types de blocks qu'Alfred émet (`header`/`section` :
types de texte autorisés, longueur max), et `tests/_block_kit.
assert_valid_block_kit_payload` les vérifie structurellement. Documenté
honnêtement ici : ce n'est pas « le validateur officiel Slack », qui
n'existe pas sous cette forme — c'est un contrat vérifié dérivé de leur
documentation publique. Choix conservateur suivant CLAUDE.md (« pas de
dépendance sans justification écrite ») en l'absence de confirmation
explicite sur l'alternative avec dépendance.

**8. Client HTTP Slack — mêmes patterns que Brique 4, pas de code
partagé entre les deux.** `alfred.deliver.slack` a son propre
`HTTPRequest`/`Transport`/`_urllib_transport`, structurellement
identiques à `alfred.narrate.llm`. Pas d'extraction dans un module HTTP
partagé : les deux call sites ont des besoins de parsing de réponse
différents (`narrate` extrait `choices[0].message.content`, `slack` n'a
qu'à vérifier un statut 2xx), et chaque module porte déjà sa propre
erreur typée (`NarrateError`, `DeliverError`) suivant la convention
établie (`MandateError`, `ReportError`). Une duplication de ~20 lignes
de boilerplate `urllib` ne justifie pas une abstraction commune.

## Conséquences

- `pyproject.toml` inchangé : aucune nouvelle dépendance de production ni
  de dev pour cette brique.
- `src/alfred/config.py`, `src/alfred/watch.py`, `src/alfred/deliver/
  {__init__.py, stdout.py, slack.py}` ajoutés ; `src/alfred/cli.py`
  réécrit avec des sous-commandes argparse (`init`, `watch`, `demo` en
  stub) déléguant à ces modules.
- Tests falsifiables : `tests/test_config.py`, `tests/test_watch.py`,
  `tests/test_deliver_stdout.py`, `tests/test_deliver_slack.py` (incluant
  le test littéral de PLAN.md `test_slack_payload_is_valid_block_kit` et
  le test d'intégration bout-en-bout fixture trace → digest → payload,
  sans appel réseau réel via un `Transport` fake), `tests/test_cli.py`.
- `pytest -q`, `ruff check .` et `mypy --strict src/` sont verts sur tout
  le code ajouté par cette brique (9 erreurs mypy pré-existantes dans
  `tests/conftest.py` et `tests/test_trace_ingest.py`, non liées à cette
  brique, non touchées ici — modifications chirurgicales).
- Un utilisateur qui veut un vrai `watch` continu (démon, polling) doit
  encore le scripter lui-même (cron + `alfred watch`) — non encodé dans
  `watch_once` (pas de fonctionnalité hypothétique ajoutée).

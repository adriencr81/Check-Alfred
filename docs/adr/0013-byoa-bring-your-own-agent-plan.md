# 0013 — Sprint S1 « Bring Your Own Agent » : Alfred fonctionne pour les agents d'un dev externe

**Date** : 2026-07-20 · **Statut** : Accepté · **Signé** : Adrien (demande
produit), Claude Code (audit + conception)

## Contexte

Le run réel de la Brique 7 est exécuté (2026-07-20) : le refund-bot a
accordé le remboursement de 250 €, `alfred watch` a attrapé la déviation
`forbidden_action` et le digest a été livré dans Slack. Le verrou de
l'ADR 0010 est levé.

Demande utilisateur du 2026-07-20 : « le produit doit fonctionner pour un
dev qui le télécharge sur GitHub pour *ses* agents ». Audit du code fait le
même jour — trois écarts empêchent aujourd'hui un agent externe de
fonctionner de bout en bout :

1. **Pas d'API d'instrumentation publique.** La seule recette pour émettre
   une trace ingestible est `examples/agents/refund_bot/tracer.py`
   (~150 lignes, example-only). Un dev doit la copier-coller.
2. **Mandat non générique.** Le DSL `forbidden_actions` ne connaît qu'une
   forme, `<tool>_above_<montant>_eur`, câblée sur l'attribut maison
   `tool.arguments.amount_eur` (`engine.py:17,21`). Aucune règle possible
   sur un autre argument d'outil. Pire : `_check_budget_exceeded` et la
   métrique `budget_used` ne lisent que `gen_ai.usage.cost_eur` (clé
   maison) — une trace OTel standard (tokens + modèle, sans cost_eur) donne
   un budget consommé de 0 €, silencieusement, alors que `report/build.py`
   sait déjà calculer ce coût depuis les tokens.
3. **Ingestion intolérante au monde réel.** `ingest_otlp_file` fait un
   `json.loads` du fichier entier — le file exporter de l'OTel Collector
   émet du JSON ligne par ligne (NDJSON), donc le pont « agent OTel →
   Collector → fichier → alfred watch » casse. Les erreurs d'outil ne sont
   détectées que via `tool.result.status` (maison), jamais via le
   `status.code` OTLP standard.

## Décisions

**1. Sprint S1 (Briques 8-11) inséré dans PLAN.md §12, version 1.2.**
Quatre briques dans l'ordre de valeur : B8 SDK d'instrumentation public
(`alfred.instrument`), B9 mandat générique + coût depuis tokens, B10
ingestion NDJSON + mapping semconv standard, B11 onboarding + « test
5 minutes BYOA ». Contrats détaillés (tests falsifiables, DoD) dans §12 —
ce document n'enregistre que les arbitrages.

**2. Le SDK d'instrumentation est une promotion, pas une réécriture.**
`alfred.instrument` reprend la forme prouvée de `tracer.py` (émission OTLP
JSON directe, mêmes clés que l'ingestion — la neutralisation du risque
semconv de l'ADR 0010 reste valable). Le refund-bot est refondu pour le
consommer : ses 6 tests existants, inchangés, servent de preuve de parité.
Zéro dépendance nouvelle (stdlib uniquement).

**3. Le DSL string existant est conservé, la forme structurée s'y ajoute.**
`forbidden_actions` accepte en plus une entrée YAML structurée
(`tool:` + `when: args.<clé> <op> <valeur>`). `refund-bot.yaml` continue de
fonctionner tel quel — rétrocompatibilité prouvée par les tests B2
existants, non modifiés.

**4. Le coût devient un calcul partagé.** La logique tokens×modèle de
`report/build.py` est extraite vers un module commun (`alfred.trace.cost`)
consommé par le report ET le moteur de mandat. Priorité inchangée :
`gen_ai.usage.cost_eur` explicite d'abord, table de prix en repli.

**5. Le mapping semconv standard vit dans l'ingestion, pas dans le moteur.**
Conformément au garde-fou §9 du plan (« isoler l'ingestion derrière une
couche d'adaptation ») : `status.code == ERROR` → `tool.result.status =
"error"` (si absent), `gen_ai.tool.call.arguments` (string JSON) →
`tool.arguments.<clé>` scalaires. Le moteur de mandat ne change pas de
vocabulaire.

**6. Calendrier : B8 + B11 sont sur le chemin critique du launch.** Le
premier commentaire HN essaiera de brancher *son* agent ; sans API publique
ni doc BYOA, le « test 5 minutes » échoue pour tout le monde sauf nous.
Recommandation : launch maintenu au 4 août si B8 + B11 sont verts au
1er août, sinon glissement d'une semaine (11 août). B9 et B10 peuvent
atterrir la semaine du launch. **Décision de date : Adrien.** Les
non-objectifs du backlog §10 (endpoint OTLP HTTP, connecteurs natifs,
dashboard) restent en v0.2+.

## Conséquences

- PLAN.md passe en v1.2 : §12 ajouté, note de révision en tête.
- Nouveaux modules prévus : `src/alfred/instrument/`, `src/alfred/trace/cost.py`
  (extraction), extensions de `mandate/model.py`, `mandate/engine.py`,
  `trace/ingest.py` — chacun dans sa brique, un commit par brique.
- Le sprint S0 (§11) reste inchangé et parallélisable : PyPI rc1, org
  GitHub, GIF (matière disponible depuis le run du 2026-07-20), good first
  issues.

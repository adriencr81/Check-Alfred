# 0003 — `SpanKind` dérivé de `gen_ai.operation.name`

**Date** : 2026-07-16 · **Statut** : Accepté · **Signé** : Claude Code (Brique 1)

## Contexte

`ingest_otlp_json` doit classer chaque span en `SpanKind`
(`LLM_CALL` / `TOOL_CALL` / `AGENT_TASK` / `UNKNOWN`) — cette classification
est un choix d'architecture qui influence directement la Brique 2 (le moteur
de mandat doit distinguer les appels d'outils pour la déviation
`tool_not_allowed`).

Une première implémentation classait par préfixe de clé d'attribut
(`gen_ai.*` → LLM, `tool.*` → TOOL, `agent.*` → AGENT), avec une fixture de
test inventant des clés `tool.*`/`agent.*` non-standard. La review senior
IVVQ a signalé un défaut MAJOR : dans les semantic conventions OTel GenAI
réelles, les spans tool et agent portent eux aussi des attributs sous
l'espace de noms `gen_ai.*` (`gen_ai.tool.name`, `gen_ai.agent.name`,
`gen_ai.operation.name=execute_tool`). Comme le check `gen_ai.*` passait en
premier, un vrai span tool aurait été classé à tort `LLM_CALL`. De plus,
`.kind` n'était couvert par aucun test falsifiable.

## Décision

`_kind()` discrimine désormais uniquement sur la valeur de l'attribut
`gen_ai.operation.name` (le discriminant officiel des semconv GenAI), via
une table de correspondance :

| `gen_ai.operation.name` | `SpanKind` |
|---|---|
| `chat`, `text_completion`, `embeddings` | `LLM_CALL` |
| `execute_tool` | `TOOL_CALL` |
| `invoke_agent`, `create_agent` | `AGENT_TASK` |
| (absent ou valeur inconnue) | `UNKNOWN` |

La fixture `tests/fixtures/otlp_sample.json` a été alignée : le span racine
porte `gen_ai.operation.name=invoke_agent` + `gen_ai.agent.name`, le span
outil porte `gen_ai.operation.name=execute_tool` + `gen_ai.tool.name`. Les
attributs applicatifs non-standard (`agent.task`, `tool.arguments.*`,
`tool.result.status`) sont conservés en complément — ils ne sont pas des
semconv mais restent utiles en aval (Brique 3, digest).

Tests falsifiables ajoutés dans `tests/test_trace_ingest.py` :
`test_ingest_kind_is_derived_from_gen_ai_operation_name` (les 3 kinds
connus sur la fixture) et `test_ingest_kind_is_unknown_without_operation_name`
(cas `UNKNOWN`).

## Conséquences

- Le classifieur est maintenant testé et aligné sur un standard externe
  plutôt que sur une convention interne inventée.
- **Impact B2** : le moteur de mandat peut se fier à `SpanKind.TOOL_CALL`
  pour la déviation `tool_not_allowed` sans hypothèse supplémentaire sur le
  format des attributs.
- Risque résiduel : si une source de traces réelle utilise une valeur de
  `gen_ai.operation.name` hors table (ex. futures opérations semconv), le
  span atterrit en `UNKNOWN` plutôt que d'échouer — comportement dégradé
  mais silencieux, à surveiller à l'intégration d'un connecteur natif (v0.2).

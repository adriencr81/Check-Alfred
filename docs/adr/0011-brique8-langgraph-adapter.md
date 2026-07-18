# 0011 — Brique 8 : couche d'adaptation semconv + exemple LangGraph

**Date** : 2026-07-18 · **Statut** : Accepté · **Signé** : Adrien (cible +
priorité « quelque chose qui fonctionne »), Claude Code (spike, conception,
implémentation)

## Contexte

La Brique 7 a prouvé Alfred contre des traces que *nous* émettons. La
promesse publique (« ingests OTLP traces ») n'avait jamais été testée
contre un instrumentor tiers. Décisions utilisateur (2026-07-18) : cible =
agent LangGraph + instrumentor OTel tiers ; la date de launch est ignorée.

**Spike empirique** (venv scratchpad) : LangGraph `create_react_agent` +
`opentelemetry-instrumentation-langchain` (OpenLLMetry 0.62.1, semconv
`opentelemetry-semantic-conventions-ai` 0.5.1) + modèle factice à tool
calls. Constats sur les spans réellement émis (confirmés dans le code
source de l'instrumentor) :

- ✅ `gen_ai.operation.name` ∈ {`chat`, `execute_tool`, `invoke_agent`} et
  `gen_ai.tool.name` : déjà exactement ce qu'Alfred lit. Le cœur de la
  thèse (détection `tool_not_allowed`) marchait sans modification.
- ✅ `gen_ai.usage.{input,output}_tokens` émis avec un vrai modèle
  (`span_utils.py:447-452`).
- ❌ Pas de `tool.result.status` — ils émettent `gen_ai.task.status` =
  `success`/`failure` (`callback_handler.py:647,1057`).
- ❌ Pas de `tool.arguments.<k>` — les args sont dans
  `gen_ai.tool.call.arguments`, un JSON contenant `input_str` (repr Python
  du dict d'arguments) + wrappers `tags`/`metadata`.
- ❌ Attributs de type tableau (`arrayValue`) → `TraceIngestionError`.
- ❌ Deux spans `invoke_agent` par invocation (workflow interne + racine)
  et un span `create_agent` à la construction du graphe → « Tasks
  completed : 3 » pour un seul ticket.

## Décisions

**1. Normalisation à la frontière d'ingestion**
(`ingest._normalize_attributes`) — c'est la « couche d'adaptation » que
PLAN.md §9 anticipait. Sur les spans `execute_tool` uniquement :
`gen_ai.task.status` → `tool.result.status` (`success`→`ok`,
sinon→`error`) ; `gen_ai.tool.call.arguments` → promotion des arguments
scalaires en `tool.arguments.<k>` (json.loads puis `ast.literal_eval`,
déballage `input_str`, wrappers `tags`/`metadata` exclus, échec de parse
silencieux). **Les clés canoniques présentes ne sont jamais écrasées** —
les traces refund_bot passent inchangées. Le moteur et le report ne lisent
donc toujours que les clés canoniques.

**2. `arrayValue` supporté par `ingest._value`** (récursif → list). Les
traces OTLP réelles en contiennent ; les rejeter cassait toute ingestion.

**3. Anti-double-comptage des tâches** (`build._tasks_completed_line`) :
seuls les events AGENT_TASK **sans ancêtre AGENT_TASK** comptent (marche
arrière via `parent_span_id`). Traces plates existantes inchangées
(snapshot vert).

**4. `create_agent` n'est plus un AGENT_TASK** (supersède l'ADR 0003 sur
ce point) : la *construction* du graphe n'est pas une tâche accomplie.
Aucun test ne figeait l'ancien mapping ; le nouveau est figé par
`test_create_agent_span_is_not_an_agent_task`.

**5. Prix Claude dans la table snapshot** (`claude-opus-4-8`,
`claude-sonnet-5`, `claude-haiku-4-5` — $/MTok publics × 0.92 USD→EUR,
même convention que l'ADR 0005) pour que la ligne Cost existe quand
l'exemple tourne avec un vrai modèle Anthropic.

**6. Fixture de régression capturée, pas écrite.**
`tests/fixtures/langgraph_otlp_sample.json` provient d'un run instrumenté
réel (scénario refund 250 € + un outil qui échoue), exporté par
l'exporteur de l'exemple. Les 9 tests de `tests/test_trace_normalize.py`
épinglent Alfred contre des émissions authentiques — le test-clé :
une trace LangGraph déclenche `forbidden_action` sous le mandat
`refund-bot.yaml` **inchangé**, ancrée sur l'event ID du span de
l'instrumentor.

**7. L'exemple** (`examples/agents/langgraph_refund_bot/`) réutilise les
outils/données/prompt du refund_bot (même scénario, autre framework —
démonstration d'agnosticisme) ; `otlp_file.py` est un SpanExporter
générique ReadableSpan → OTLP JSON, le pont réutilisable « point your OTel
traces at Alfred ». Dépendances (`langgraph`, `langchain-anthropic`,
`opentelemetry-sdk`, `opentelemetry-instrumentation-langchain`)
strictement example-only — rien n'entre dans pyproject (ni prod ni dev).

## Limites honnêtes

- L'heuristique `input_str` est propre à OpenLLMetry ; OpenInference/openlit
  ont d'autres formes → v0.2, priorisés par issues.
- `gen_ai.agent.name` vaut « LangGraph » (nom de graphe par défaut) ; le
  digest ne filtre pas par nom d'agent (contrat existant de
  `build_digest` : le scoping appartient à l'appelant).
- La fixture pèse ~220 Ko (payloads `traceloop.entity.*` inclus) —
  conservée telle quelle par fidélité aux émissions réelles.
- `docs/vcd/alfred-v0.1.md` (compte de tests, tableau de couverture) est
  périmé depuis la Brique 7 — à régénérer avant le prochain jalon public.

## Conséquences

- `src/alfred/trace/ingest.py` : `_value` (arrayValue), mapping
  `create_agent` retiré, `_normalize_attributes` + helpers.
- `src/alfred/report/build.py` : dédoublonnage des tâches imbriquées,
  entrées de prix Claude.
- Preuve : `python3 -m pytest -q` → 129 passed ; `ruff check .` et
  `python3 -m mypy --strict src/` verts ; run de bout en bout (exemple
  avec modèle factice → `alfred watch`) → digest « Tasks completed: 1 »
  + la déviation `forbidden_action` ancrée. Le run avec vrai modèle
  (`run.py`, clé API) est l'étape utilisateur.

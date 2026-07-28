# 0014 — Connecteur natif LangGraph avancé en anticipé (hors v0.2 backlog)

**Date** : 2026-07-21 · **Statut** : Accepté · **Signé** : Adrien (demande
produit + arbitrages via questions du 2026-07-21), Claude Code (audit +
conception)

## Contexte

Demande utilisateur du 2026-07-21 : « attaque la brique LangGraph ». Or le
PLAN.md verrouillé (v1.2) range explicitement les **connecteurs natifs
LangGraph/CrewAI/OpenAI en v0.2, backlog, « priorisés par les issues, pas
par intuition »** (PLAN.md §10 ligne 434, §6.4 ligne 355, et
`docs/GROWTH_PLAN_3M.md` ligne 134 : cible `pip install alfred-ai[langgraph]`,
« 3 lignes pour instrumenter, exemple complet »). Aucune « brique LangGraph »
n'est définie dans la roadmap ; les briques 1-11 (jusqu'à BYOA) sont livrées
(`main` vert, `docs/vcd/alfred-v0.1.md`).

La règle du repo impose qu'« tout écart à [PLAN.md] soit précédé d'une entrée
`docs/adr/NNNN` datée » (PLAN.md, note de fin) et que « toute décision qui
contredit ce document soit documentée dans un ADR daté » (PLAN.md §0). Cet
ADR est cette entrée : il enregistre la décision d'avancer le connecteur
LangGraph et ses arbitrages. Il ne re-planifie pas la roadmap au-delà de
cette brique.

Deux tensions à trancher, résolues par les réponses utilisateur du
2026-07-21 :

1. **Forme.** Le SDK `alfred.instrument.AgentTracer` (Brique 8) émet déjà
   l'OTLP JSON exact que lit l'ingestion. Une brique LangGraph peut être un
   connecteur natif (auto-instrumentation), un exemple à la main, ou les
   deux.
2. **Dépendance.** CLAUDE.md interdit « toute dépendance lourde sans
   justification écrite dans le plan ». LangChain/LangGraph est lourd
   (pydantic, orjson, httpx, langsmith…).

## Décisions

**1. On avance le connecteur natif LangGraph maintenant, en anticipé sur la
v0.2.** Décision produit d'Adrien. C'est un écart assumé au séquencement du
PLAN (v0.2 → maintenant), pas au reste du plan : les autres non-objectifs du
backlog §10 (endpoint OTLP HTTP, dashboard web, connecteurs CrewAI/OpenAI,
base non-SQLite) restent hors périmètre. La priorisation « par les issues »
est levée pour ce seul connecteur, à la demande explicite du fondateur.

**2. Forme retenue : connecteur natif + exemple minimal.** Un
`BaseCallbackHandler` LangChain — `alfred.integrations.langgraph` — enveloppe
`AgentTracer` : un graphe LangGraph invoqué avec ce handler émet
automatiquement une trace Alfred ingestible, sans que le dev copie du code
d'instrumentation. Plus un `examples/agents/langgraph_bot/` minimal (agent
jouet, fake chat model, zéro clé API) qui montre les « 3 lignes » promises.

**3. Le handler réutilise la forme d'émission prouvée, sans réécrire ni
modifier `tracer.py`.** Les callbacks LangChain sont pilotés par événements
(paires start/end indexées par `run_id`), alors qu'`AgentTracer` expose des
context managers. Le handler pilote ces context managers manuellement
(`cm.__enter__()` à l'événement `*_start`, `cm.__exit__()` à `*_end`),
indexés par `run_id`. Conséquence directe : la garantie « clés exactement
celles que lisent `ingest`/`engine`/`build` » (neutralisation du risque
semconv, ADR 0010/0013) est héritée mécaniquement — aucune clé n'est
réémise à la main dans le connecteur. `tracer.py` n'est pas touché.

**4. Mapping des événements → spans Alfred, ancré sur des faits réels de la
trace LangGraph (règle produit D5) :**
- premier `on_chain_start` racine (`parent_run_id is None`) → `session()`
  (`invoke_agent`) ; son `on_chain_end`/`on_chain_error` ferme la session ;
- `on_chat_model_start`/`on_llm_start` → `llm_call()` ; `on_llm_end` →
  `record_usage(...)` depuis les tokens réels de la réponse
  (`usage_metadata`/`llm_output`), sans invention ;
- `on_tool_start` → `tool_call(name, arguments)` (nom depuis `serialized`,
  arguments depuis `inputs`) ; `on_tool_end` → statut `ok` ; `on_tool_error`
  → statut `error`.
  Aucune affirmation dérivée : chaque span porte l'`event_id` LangGraph et
  des attributs mesurés.

**5. Dépendance `langchain-core` gérée comme un extra optionnel `[langgraph]`,
jamais dans le cœur.** `pip install alfred-ai` reste à `pyyaml` seul. Le
module `alfred.integrations.langgraph` importe `langchain_core` au niveau
module : il n'est donc importable que si l'extra est installé — même
discipline que la dépendance example-only `anthropic` (ADR 0010, décision 2).
Justification écrite exigée par CLAUDE.md : la dépendance *est* l'objet du
connecteur, elle est cloisonnée derrière l'extra, et le cœur n'en dépend pas.

**6. Test falsifiable = vrai graphe LangGraph, zéro réseau.** Conformément à
la philosophie de test du repo (ADR 0006, refund-bot scripté), le test monte
un vrai graphe LangGraph avec un fake chat model déterministe (fourni par
`langchain-core`) et un outil jouet, l'invoque avec le handler, puis ingère
la trace produite et vérifie : kinds corrects (`AGENT_TASK`/`LLM_CALL`/
`TOOL_CALL`), event IDs uniques, arguments d'outil aplatis, statut d'erreur
sur `on_tool_error`, et digest dont chaque ligne a `sources` non-vide. CI
installe l'extra `[langgraph]` pour exécuter ce test ; le cœur et les autres
tests n'en dépendent pas.

## Conséquences

- Nouveaux fichiers : `src/alfred/integrations/__init__.py`,
  `src/alfred/integrations/langgraph.py`, `examples/agents/langgraph_bot/`,
  `tests/test_integration_langgraph.py`.
- `pyproject.toml` : extra `[project.optional-dependencies] langgraph`,
  override mypy pour `langchain_core`/`langgraph` si nécessaire, extra
  installé dans le job de test CI.
- `tracer.py` **inchangé** (décision 3). `alfred.instrument` reste le socle.
- PLAN.md : une brique dédiée est ajoutée en §12 (contrat : objectif, tests
  falsifiables, DoD) et la note de révision en tête référence cet ADR — la
  roadmap reste la source de vérité unique.
- Le reste du backlog §10 est explicitement maintenu hors périmètre : cet
  ADR n'ouvre pas la porte aux autres connecteurs ni au dashboard.
- Un commit par brique cohérente, exigences §5/§12 inchangées (`pytest -q`,
  `ruff check .`, `mypy --strict src/` verts à la DoD).

# 0021 — Connecteur natif OpenAI Agents SDK (F5, première moitié)

**Date** : 2026-07-23 · **Statut** : Accepté · **Signé** : Adrien (demande
produit « démarre la brique F5 »), Claude Code (audit + conception)

## Contexte

Demande du fondateur du 2026-07-23 : « démarre la brique F5 du plan ». La
feature F5 (PLAN.md §13) est : **« Connecteurs natifs CrewAI + OpenAI Agents
SDK — la recette du connecteur LangGraph (Brique 12) pour les deux autres
frameworks dominants »**, roadmapée v0.2 (« priorisée par les issues »).

Le connecteur LangGraph (Brique 12, ADR 0014) a établi la recette : un
adaptateur natif du framework qui pilote les context managers prouvés
d'`AgentTracer` (`alfred.instrument`) sans réécrire ni modifier `tracer.py`,
cloisonné derrière un extra optionnel, avec un test falsifiable qui monte un
vrai run du framework, zéro réseau. Cet ADR applique cette recette à
l'**OpenAI Agents SDK** (`openai-agents`, module d'import `agents`).

Deux tensions, tranchées comme pour LangGraph :

1. **Surface d'instrumentation.** L'OpenAI Agents SDK expose un système de
   *tracing* natif : un `Runner.run(...)` émet une `Trace` (le run entier) et
   des `Span` typés (`GenerationSpanData`/`ResponseSpanData` pour les appels
   modèle, `FunctionSpanData` pour les outils), livrés à tout
   `TracingProcessor` enregistré. C'est le point d'accroche naturel — l'exact
   analogue des callbacks LangChain.
2. **Dépendance.** CLAUDE.md interdit « toute dépendance lourde sans
   justification écrite dans le plan ». `openai-agents` est lourd (tire
   `openai`, `mcp`, `pydantic`, `starlette`…).

## Décisions

**1. On livre le connecteur OpenAI Agents SDK maintenant ; CrewAI (l'autre
moitié de F5) reste hors périmètre de cette brique.** Décision de séquencement
du fondateur, comme l'anticipation LangGraph (ADR 0014). F5 se scinde en deux
briques cohérentes (« un commit par brique cohérente », CLAUDE.md) : OpenAI
Agents d'abord (dépendance plus légère que CrewAI, hooks de tracing natifs les
plus propres), CrewAI ensuite. Le reste du backlog §10 (endpoint OTLP HTTP,
dashboard web, base non-SQLite) reste hors périmètre.

**2. Forme retenue : connecteur natif + exemple minimal.** Un
`TracingProcessor` — `alfred.integrations.openai_agents.AlfredTracingProcessor`
— enveloppe `AgentTracer`. On l'enregistre une fois
(`set_trace_processors([AlfredTracingProcessor(tracer)])` pour un run 100 %
hors-ligne, ou `add_trace_processor(...)` en plus de l'export OpenAI natif) et
tout `Runner.run(...)` émet automatiquement une trace Alfred ingestible. Plus
un `examples/agents/openai_agents_bot/` minimal (client OpenAI factice sur un
transport HTTP simulé, zéro clé API, zéro réseau).

**3. Le processor réutilise la forme d'émission prouvée, sans toucher
`tracer.py`.** Le tracing du SDK est piloté par événements (`on_trace_start`/
`on_trace_end`, `on_span_start`/`on_span_end`), alors qu'`AgentTracer` expose
des context managers. Le processor pilote ces context managers manuellement,
indexés par `trace_id`. Conséquence directe : la garantie « clés exactement
celles que lisent `ingest`/`engine`/`build` » (ADR 0010/0013/0014) est héritée
mécaniquement — aucune clé n'est réémise à la main. `tracer.py` est inchangé.

**4. Mapping des événements → spans Alfred, ancré sur des faits réels de la
trace (règle produit D5) :**
- `on_trace_start` racine → `session()` (`invoke_agent`) ; `on_trace_end` la
  ferme. Une `Trace` = un `Runner.run` = une tâche d'agent.
- `GenerationSpanData` / `ResponseSpanData` (chemins Chat Completions et
  Responses API) → `llm_call()` ; les tokens réels sont lus depuis
  `span_data.usage` (`input_tokens`/`output_tokens`, forme partagée par les
  deux chemins), sans invention.
- `FunctionSpanData` → `tool_call(name, arguments)` : nom depuis
  `span_data.name`, arguments parsés depuis le JSON `span_data.input` puis
  aplatis en `tool.arguments.<clé>` par `AgentTracer`. Statut `error` si le
  span porte une erreur (`span.error`), sinon `ok`.
- Les autres spans (`AgentSpanData`, `TurnSpanData`, `TaskSpanData`,
  handoffs, guardrails…) sont **ignorés** : ils ne portent pas de fait
  mesuré neuf pour le mandat, et `TurnSpanData` reporte l'usage déjà compté
  par le span de génération — les mapper doublerait le décompte de tokens.

  L'enregistrement se fait à `on_span_end` : c'est le seul moment où le SDK a
  peuplé `usage`, `input` (arguments outil) et `error`.

**5. Différence assumée avec LangGraph — l'erreur d'outil n'est pas fatale.**
Par défaut, l'OpenAI Agents SDK **capture** l'exception d'un outil (« error
running tool (non-fatal) »), la reporte au modèle et poursuit le run ; elle
n'est pas propagée. Le connecteur la lit sur `span.error` du `FunctionSpanData`
et la mappe en `tool.result.status: error`. Le run se termine normalement (pas
de `raise`) — le test le reflète, au lieu d'attendre une exception comme le
test LangGraph.

**6. Dépendance `openai-agents` gérée comme un extra optionnel
`[openai-agents]`, jamais dans le cœur.** `pip install alfred-ai` reste à
`pyyaml` seul. Le module `alfred.integrations.openai_agents` importe `agents`
au niveau module : il n'est donc importable qu'avec l'extra installé — même
discipline que `[langgraph]` (ADR 0014, décision 5). Justification écrite
exigée par CLAUDE.md : la dépendance *est* l'objet du connecteur, elle est
cloisonnée derrière l'extra, et le cœur n'en dépend pas. La CI installe
`.[dev]` (qui tire l'extra) pour exécuter le test e2e à chaque push.

**7. Test falsifiable = vrai `Runner.run`, zéro réseau.** Comme pour LangGraph,
le test monte un vrai agent OpenAI Agents SDK avec un vrai
`OpenAIChatCompletionsModel` branché sur un client `AsyncOpenAI` factice
(transport `httpx.MockTransport` renvoyant des réponses canned, aucune clé,
aucun réseau). Les spans de génération et de fonction sont créés par le SDK
lui-même (pas fabriqués à la main). Le test ingère la trace produite et
vérifie : kinds corrects (`AGENT_TASK`/`LLM_CALL`/`TOOL_CALL`), event IDs
uniques, arguments d'outil aplatis, statut `error` sur outil en échec, usage
LLM propagé, digest dont chaque ligne a `sources` non-vide ⊆ event IDs, et
qu'une approbation à 250 € sous mandat cap 100 € produit exactement une
`Deviation FORBIDDEN_ACTION` ancrée sur l'event ID du tool call.

## Conséquences

- Nouveaux fichiers : `src/alfred/integrations/openai_agents.py`,
  `examples/agents/openai_agents_bot/`,
  `tests/test_integration_openai_agents.py`.
- `pyproject.toml` : extra `[project.optional-dependencies] openai-agents`,
  ajouté à `dev` (donc installé en CI), override mypy pour `agents.*` si
  nécessaire.
- `tracer.py` **inchangé** (décision 3). `alfred.instrument` reste le socle.
- PLAN.md : une brique dédiée est ajoutée en §12 (contrat : objectif, tests
  falsifiables, DoD) et §13 note F5 démarrée (OpenAI Agents livré, CrewAI
  restant). La roadmap reste la source de vérité unique.
- Le reste de F5 (CrewAI) et du backlog §10 restent explicitement hors
  périmètre : cet ADR n'ouvre pas la porte aux autres connecteurs ni au
  dashboard.
- Exigences §5/§12 inchangées (`pytest -q`, `ruff check .`,
  `mypy --strict src/` verts à la DoD).

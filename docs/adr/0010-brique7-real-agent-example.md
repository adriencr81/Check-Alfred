# 0010 — Brique 7 : premier agent réel vérifié par Alfred

**Date** : 2026-07-18 · **Statut** : Accepté · **Signé** : Adrien (décisions
stack + calendrier), Claude Code (conception + implémentation)

## Contexte

Constat utilisateur post-v1.1 : « j'ai du code, mais pas de démo et je n'ai
pas encore créé d'agent à qui je confie une tâche que je vérifie ».
`alfred demo` (ADR 0008) rejoue un payload OTLP codé en dur — il prouve le
pipeline, pas la thèse. La phrase qui EST le produit — *confier une tâche à
un agent sous mandat et attraper son écart* — n'avait jamais eu lieu avec un
agent réel. Deux décisions utilisateur (2026-07-18) cadrent cette brique :

1. **Stack** : boucle d'outils Claude sans framework (API Anthropic
   directe), pas OpenAI Agents SDK ni LangGraph ni dogfooding Claude Code.
2. **Calendrier** : brique 7 d'abord ; la date de launch du 4 août
   (ADR 0009) est **suspendue** et sera re-datée sur preuve d'un run réel
   de bout en bout — pas sur estimation.

## Décisions

**1. Émission OTLP JSON directe, pas le SDK OTel.** Le SDK Python n'a pas
d'exporteur fichier OTLP-JSON stable, et le risque §9 du plan (« semconv
GenAI mouvantes ») se neutralise en émettant exactement les clés que
`alfred.trace.ingest` et `alfred.mandate.engine` lisent
(`gen_ai.operation.name`, `gen_ai.tool.name`, `tool.result.status`,
`tool.arguments.amount_eur`, `gen_ai.usage.*`). Ce qui est réel : les
décisions du modèle, les exécutions d'outils et leurs erreurs, les span
IDs, les timestamps, l'usage de tokens. Ce qui est à nous : uniquement la
sérialisation (`tracer.py`, ~150 lignes, forme calquée sur
`tests/fixtures/otlp_sample.json`). Le README de l'exemple l'assume
honnêtement (tableau « What's real, what's fake »).

**2. `anthropic` reste une dépendance d'exemple, jamais du paquet.**
`agent.py` définit un Protocol `LLMClient` ; `run.py` est le seul fichier
qui importe `anthropic` (lazy, dans le constructeur, message clair si
absent). Les tests n'utilisent que le Protocol avec un `ScriptedClient` —
zéro réseau en CI, même philosophie que les fakes de l'ADR 0006/0007.
`pyproject.toml` gagne uniquement : `mypy_path = ["examples/agents"]`
(pour que mypy résolve et vérifie strictement l'exemple importé par le
test) et un override `ignore_missing_imports` pour `anthropic`. Aucune
dépendance de production ni de dev ajoutée.

**3. Le prompt système ne restate PAS le mandat.** Le refund-bot reçoit un
prompt ops plausible (« sois utile, les remboursements complets sont
appropriés pour les défauts produits ») sans plafond ni liste interdite.
C'est le point produit : un prompt n'est pas une politique ; le mandat est
une supervision externe de ce qui s'est réellement passé. Le ticket TCK-2
(remboursement de 250 € sur une commande de 250 €) *tente* l'agent sans
lui dicter sa réponse — en run réel, l'issue appartient au modèle.

**4. Modèle par défaut `claude-opus-4-8`** (guidance API Anthropic
courante ; surchargeable par `--model`). Coût attribué en émettant
`gen_ai.usage.cost_eur` calculé côté exemple (table $/MTok × taux
USD→EUR fixe documenté) — prioritaire dans `report/build.py`, donc la
table de prix du produit n'est pas touchée.

**5. Les tests scriptés prouvent le contrat, le run réel prouve la démo.**
`tests/test_example_refund_bot.py` (6 tests, `ScriptedClient`) garantit :
trace ingestible (kinds/attributs/IDs uniques), `tool.arguments.amount_eur`
présent sur `issue_refund`, usage réel propagé, **un run à 250 € produit
exactement une déviation `forbidden_action` ancrée sur l'event ID du tool
call réel** (le test qui incarne la brique), miroir conforme à 40 € sans
déviation, erreur d'outil → `tool.result.status != "ok"`. Le run réel
(`run.py`, nécessite une clé API) est l'étape utilisateur qui produira le
GIF et re-datera le launch.

## Conséquences

- Nouveaux fichiers : `examples/agents/refund_bot/{__init__,agent,tools,
  tracer,run}.py`, `orders.json`, `tickets.json`, `README.md`,
  `tests/test_example_refund_bot.py`, ce document.
- `src/alfred/` inchangé — la brique n'a exigé aucune modification du
  produit, ce qui valide au passage les contrats d'ingestion/mandat.
- `pytest -q` : 118 tests verts ; `ruff check .` et `mypy --strict src/`
  verts.
- Dette notée (préexistante, hors périmètre) : `python3 -m mypy` en mode
  config (qui inclut `tests/`) échoue sur 9 erreurs dans
  `tests/conftest.py` et `tests/test_trace_ingest.py`, présentes sur main
  avant cette brique ; la commande officielle `mypy --strict src/` et la
  CI restent vertes.
- Le launch reste non daté tant que le run réel n'a pas été exécuté et le
  GIF enregistré (décision utilisateur, supersède la date ADR 0009).

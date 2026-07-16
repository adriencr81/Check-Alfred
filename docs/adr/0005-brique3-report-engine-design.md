# 0005 — Conception du moteur de rapport (Brique 3)

**Date** : 2026-07-16 · **Statut** : Accepté · **Signé** : Claude Code (Brique 3)

## Contexte

Le PLAN.md (§5, Brique 3) fixe le format de sortie du digest et les trois
tests falsifiables (`every_line_has_sources`, `sources_exist_in_store`,
`cost_matches_sum`), mais laisse ouverts des points déjà signalés par l'ADR
0004 : le vrai calcul tokens→€ (explicitement différé à cette brique), et
aucun signal de trace ne marque la réussite d'une tâche agent. Deux
décisions ont été tranchées avec l'utilisateur avant implémentation ; une
troisième (format de rendu multi-déviations, non spécifié par PLAN.md) a été
tranchée ici et documentée, suivant le même principe que l'ADR 0004.

## Décisions

**1. Coût par event (v0.1 réel)** — `alfred.report.build._event_cost_eur`
utilise `gen_ai.usage.cost_eur` s'il est présent (comme le moteur de
mandat), sinon calcule à partir de `gen_ai.usage.input_tokens` /
`output_tokens` via une table de prix `_PRICING_EUR_PER_1K_TOKENS` (€/1K
tokens, indexée par `gen_ai.response.model`), sinon `0.0`. Table initiale :
`gpt-4o-mini(-2024-07-18)` et `gpt-4o(-2024-08-06)`, valeurs approximatives
de tarification publique, à étendre au fil des modèles rencontrés — risque
accepté (comme pour B2) : un modèle absent de la table et sans
`cost_eur` contribue 0€, silencieusement.

**2. Tasks completed** — chaque event `SpanKind.AGENT_TASK` compte comme une
tâche complétée, sans signal de succès/échec (aucune convention de ce type
n'existe dans l'ingestion). Décision utilisateur explicite, confirmée avant
implémentation.

**3. Lignes à zéro omises, pas vides** — `Line.sources` doit toujours être
non-vide (même contrat que `Deviation.event_ids`, `mandate/model.py:60-68`).
Plutôt que d'émettre une `Line` à valeur 0 sans source, `build_digest` omet
la ligne correspondante quand aucun event n'y contribue (ex. aucun
`AGENT_TASK` → pas de ligne `tasks_completed`). Cohérent avec
`mandate.engine.evaluate` qui retourne déjà `[]` plutôt qu'une `Deviation`
vide quand rien n'est détecté.

**4. Signature `build_digest(mandate, events, on)`** — PLAN.md §3 ne fixe
que le flux « events + mandate → Digest », pas une signature. La date ne
peut pas être déduite sans ambiguïté de `events` (aucune garantie qu'ils
soient bornés à un jour calendaire précis) : `on: date` est un paramètre
explicite. `events` doit être pré-filtré par l'appelant à un agent / un jour
(même précondition que celle déjà documentée sur `evaluate` pour un seul
trace). En interne, `build_digest` regroupe `events` par `trace_id` avant
d'appeler `evaluate` par trace (un jour comporte typiquement plusieurs
traces = plusieurs tâches), puis concatène les `Deviation` obtenues.

**5. Rendu des déviations** — non spécifié par PLAN.md au-delà de l'exemple
à une seule déviation. Une seule déviation : ligne unique reproduisant
exactement l'exemple PLAN.md (`Deviations (mandate): 1   [evt:d0a] —
tool_not_allowed: ...`). Plusieurs déviations : une ligne d'en-tête avec le
compte total, suivie d'une puce par déviation (réutilisant son `.message`
déjà formé). Zéro déviation : section entièrement omise.

## Conséquences

- `alfred.report.model.Digest` réutilise `alfred.mandate.model.Deviation`
  tel quel plutôt que de dupliquer un type de ligne dédié — il porte déjà
  `type`, `event_ids`, `message` et garantit déjà des ancres non-vides.
- `alfred.report.build.build_digest` ne dépend pas de `alfred.trace.store` :
  comme `mandate.engine.evaluate`, il opère sur une liste d'events déjà
  filtrée par l'appelant. Le filtrage par agent/jour via le store viendra
  avec la CLI (B5), pas ici.
- Tests falsifiables : `tests/test_report_model.py` (invariant `Line`),
  `tests/test_report_build.py` (les trois tests PLAN.md + couverture par
  ligne + regroupement multi-traces + snapshot d'une fixture « journée
  type »), `tests/test_report_render.py` (format figé, cas 0/1/N
  déviations).

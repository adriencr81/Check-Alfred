# 0004 — Conception du moteur de mandat (Brique 2)

**Date** : 2026-07-16 · **Statut** : Accepté · **Signé** : Claude Code (Brique 2)

## Contexte

Contrairement à la Brique 1, le PLAN.md (§5, Brique 2) ne fixe pas le
mécanisme d'évaluation : il donne le format du mandat, les 4 types de
déviation (`tool_not_allowed`, `budget_exceeded`, `forbidden_action`,
`escalation_missed`) et l'exemple `refund-bot.yaml`, sans préciser comment
interpréter des entrées comme `issue_refund_above_100_eur`, comment
calculer un coût par event (aucune pricing table n'existe encore — elle est
prévue en Brique 3, module `report`), ni quel signal de trace marque une
escalade. Ces trois points ont été tranchés avec l'utilisateur avant
implémentation.

## Décisions

**1. DSL `forbidden_actions`** — une entrée de la forme
`<outil>_above_<seuil>_eur` (regex `^(?P<tool>.+?)_above_(?P<amount>\d+(?:\.\d+)?)_eur$`,
`tool` capturé en mode paresseux) est interprétée comme : l'appel de
`<outil>` est interdit si son attribut `tool.arguments.amount_eur` dépasse
`<seuil>`. Une entrée qui ne matche pas ce motif reste un nom d'outil
interdit exact (tout appel de cet outil est une déviation). Couvre
`issue_refund_above_100_eur` et `send_marketing` sans DSL générique
sur-conçue.

**2. Coût par event (v0)** — `alfred.mandate.engine` lit l'attribut
`gen_ai.usage.cost_eur` déjà présent sur les events (posé par
l'ingestion/producteur de trace) et le somme sur le trace pour
`budget_exceeded` et la métrique `budget_used` d'`escalate_when`. Le vrai
calcul tokens→€ (table de prix par modèle) est **explicitement différé à la
Brique 3** (module `report`, cf. PLAN.md §3 « Cost (tokens → €) »). Risque
accepté : tant qu'aucun producteur de trace réel ne pose cet attribut, le
budget engine ne détecte rien — comportement dégradé mais silencieux, à
lever dès l'intégration B3.

**3. Signal d'escalade** — convention explicite : tout event du trace
portant l'attribut booléen `alfred.escalated=true` signale qu'une escalade
a eu lieu. Préféré à la réutilisation d'un outil métier (ex.
`notify_customer`) car un outil `allowed_tools` peut être appelé pour des
raisons non liées à une escalade — l'attribut dédié ne détourne aucune
sémantique existante et reste simple à poser côté instrumentation.

**4. Dépendance PyYAML** — `pyyaml>=6.0` ajoutée aux dépendances du paquet
(`pyproject.toml`), plus `types-PyYAML` en dev pour `mypy --strict`.
Justification : le format déclaratif du mandat est du YAML par décision
produit (PLAN.md §5), PyYAML est la bibliothèque de référence, sans
dépendance transitive lourde.

## Conséquences

- `alfred.mandate.engine.evaluate(mandate, events)` opère sur les events
  **d'un seul trace** (le caller filtre au préalable, ex. via
  `TraceStore.find_by_trace` — Brique 1). Ce n'est pas un choix
  d'agrégation multi-jours ; ça viendra avec le module `report` (B3).
- `docs/adr/0003-span-kind-classification.md` avait anticipé cette brique
  en fixant `SpanKind.TOOL_CALL` comme discriminant fiable pour
  `tool_not_allowed` — confirmé, aucune hypothèse supplémentaire nécessaire.
- Tests falsifiables : `tests/test_mandate_engine.py` (un test déclencheur
  + un miroir par type de déviation, plus `test_deviation_carries_event_ids_present_in_trace`),
  `tests/test_mandate_yaml.py` (roundtrip + chargement de l'exemple public
  `examples/mandates/refund-bot.yaml` + erreurs `MandateError`).

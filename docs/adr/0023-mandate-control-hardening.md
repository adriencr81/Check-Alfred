# 0023 — Durcissement des contrôles du mandat (l'agent est l'adversaire)

**Date** : 2026-07-25 · **Statut** : Accepté · **Signé** : Adrien (demande
produit « trouve-moi les failles, puis attaque les corrections par lot »),
Claude Code (pentest + conception)

## Contexte

Pentest en boîte blanche du 2026-07-25. Constat de fond : jusqu'ici le moteur
lisait la trace comme une source *coopérative*. Or Alfred est une couche de
contrôle, donc son adversaire principal est **l'agent audité lui-même** — qui
écrit 100 % de l'entrée (`spanId`, noms d'outils, attributs, coûts). Cinq
contournements ont été reproduits par PoC exécuté :

1. **Budget par trace, pas par jour.** `report/build.py::_deviations` groupe les
   événements par `trace_id` puis appelle `evaluate` trace par trace, donc
   `_check_budget_exceeded` somme une seule trace. Or `AgentTracer.session()`
   ouvre un `trace_id` neuf par tâche. PoC : 10 sessions × 4,90 € contre un
   `daily_budget_eur: 5.00` → digest affichant 49 €, **zéro déviation**. Le
   README (« the day's token → € cost ») décrivait déjà le comportement attendu :
   le code ne le tenait pas.
2. **Coût auto-déclaré.** `trace/cost.py::event_cost_eur` donnait la priorité à
   `gen_ai.usage.cost_eur`. PoC : 4M tokens in + 2M out sur `claude-opus-4-8`
   (~70 € au tarif de la table) déclarés `cost_eur: 0.0` → la ligne coût
   **disparaît** du digest et le budget n'est jamais dépassé.
3. **Escalade auto-attestée.** `_is_escalated` cherchait `alfred.escalated is
   True` sur n'importe quel span. L'agent surveillé écrivait donc lui-même
   l'attribut qui désarme la surveillance : PoC 100 % d'erreurs outil +
   `alfred.escalated: true` → `escalation_missed` s'évapore, et il gagne en
   prime une ligne « Escalations: 1 » flatteuse.
4. **Fail-open à la classification.** Un span dont `gen_ai.operation.name` est
   inconnu tombait en `UNKNOWN` (donc hors de tous les contrôles outil), et un
   `TOOL_CALL` sans `gen_ai.tool.name` était silencieusement ignoré
   (`if tool is not None and ...`). PoC : le même appel interdit passe sous
   `operation.name: tool.execute`, ou en omettant simplement le nom d'outil.
5. **Confusion de types.** `_rule_matches` ne déclenchait que sur `int | float` ;
   OTLP autorise `stringValue`. PoC : `amount_eur: "9999"` (chaîne) passe sous
   une règle `args.amount_eur > 1000`.

Les quatre premiers violent frontalement la règle produit absolue de
`CLAUDE.md` : une affirmation du rapport (le coût, l'escalade) ou l'absence
d'une déviation y dépendait d'une **déclaration de l'agent**, pas d'un fait
calculé depuis un événement identifiable.

## Décisions

**1. Deux portées d'évaluation, explicites.** `mandate.engine` expose
`evaluate_trace` (contrôles dont la sémantique est intra-trace :
`tool_not_allowed`, `forbidden_action`, `required_action_missing`,
`loop_detected`) et `evaluate_day` (contrôles agrégés : `budget_exceeded`,
`escalation_missed`, `cost_mismatch`). `evaluate` reste exporté et compose les
deux, donc le contrat public « évalue cet ensemble d'événements » ne change
pas. `report/build.py` boucle la première par `trace_id` et n'appelle la
seconde qu'**une fois par jour**. Alternative écartée : faire de `evaluate` la
fonction jour et supprimer la portée trace — casserait `required_actions` et
`loop_detected`, dont la sémantique documentée est « dans la même trace ».

**2. Le coût calculé fait foi ; le coût déclaré est un repli.** Quand le modèle
est dans `_PRICING_EUR_PER_1K_TOKENS` et que les tokens sont présents, le coût
est **calculé** ; `gen_ai.usage.cost_eur` ne sert que si le coût n'est pas
calculable (modèle inconnu, tokens absents). Inverse la décision de l'ADR 0005
(« un `cost_eur` explicite l'emporte toujours »), assumé : cette priorité
faisait du chiffre le plus visible du digest un résumé auto-déclaré.

**3. Un écart déclaré/calculé est une déviation, pas une correction
silencieuse.** Nouveau `cost_mismatch`, levé au niveau du **jour** (somme
déclarée vs somme calculée sur les événements où les deux existent) quand
l'écart dépasse 20 % *et* 0,50 € — le seuil agrégé attrape la sous-déclaration
en miettes qu'un seuil par événement laisserait passer. Corriger sans le dire
cacherait la tentative de fraude ; la remonter est précisément le produit.

**4. L'escalade se prouve par une action, pas par un booléen.** Nouveau champ
mandat `escalation_tools: [<nom>, ...]`. Une escalade est prouvée ssi la trace
contient un `TOOL_CALL` dont `gen_ai.tool.name` est dans cette liste.
`alfred.escalated` n'a plus **aucun** effet, ni sur `escalation_missed` ni sur
la ligne Escalations du digest. **Fail-closed** : un mandat déclarant
`escalate_when` sans `escalation_tools` ne peut prouver aucune escalade, donc
tout franchissement de seuil lève la déviation — et `alfred mandate lint` le
signale en **ERROR** pour que ce soit détecté avant `watch`, jamais découvert
par surprise. Alternative écartée : garder `alfred.escalated` en repli quand la
clé est absente — rétro-compatible, mais conserve la faille ouverte pour tout
mandat non migré, ce qui est exactement le trou qu'on ferme.

**5. Classification fail-closed.** `trace.ingest._kind` classe en `TOOL_CALL`
tout span portant `gen_ai.tool.name` ou un `tool.arguments.*`, même sans
`gen_ai.operation.name` reconnu (les spans OTel ordinaires — HTTP, DB — n'ont
aucun de ces attributs et restent `UNKNOWN`, donc pas de faux positif). Et un
`TOOL_CALL` sans nom résoluble lève désormais `tool_unidentified` au lieu
d'être ignoré : un outil qu'on ne peut pas nommer ne peut pas être autorisé.

**6. Comparaison numérique tolérante à la forme, stricte sur le fond.**
`_rule_matches` coerce les chaînes numériques (`"9999"` → `9999.0`). Une valeur
présente mais non convertible (`"beaucoup"`, un objet) rend la règle
invérifiable : elle lève un `forbidden_action` explicite disant que la valeur
n'a pas pu être évaluée. Faux positif possible sur un argument légitimement
textuel — assumé : une règle de police qu'on ne peut pas vérifier doit être
bruyante, jamais silencieuse.

## Règle produit (D5) — restaurée

Avant : le coût affiché et l'absence d'`escalation_missed` pouvaient provenir
d'une déclaration de l'agent. Après : le coût vient des tokens comptés sur les
spans, l'escalade d'un appel d'outil réel, et chaque nouvelle déviation
(`cost_mismatch`, `tool_unidentified`) est ancrée sur les `event_id` qui la
prouvent. Aucune affirmation du digest n'est plus auto-déclarée.

## Ruptures de compatibilité assumées

- **Coût** : un déployeur bénéficiant de tarifs négociés/cache verra le tarif
  de table faire foi, et un `cost_mismatch` s'il déclare le tarif réel. La
  table reste extensible ; un modèle absent laisse le déclaré faire foi.
- **`alfred.escalated`** : sans effet. Les mandats et intégrations doivent
  déclarer `escalation_tools` et appeler un vrai outil d'escalade. Migrés dans
  ce lot : `demo/fake_agent.py`, `examples/mandates/refund-bot.yaml`, les trois
  `examples/agents/*/mandate.yaml`, README et `docs/integrate.md`.
- **Budget** : un mandat calibré sur l'ancien comportement (budget effectif par
  tâche) lèvera désormais `budget_exceeded` — c'est le bug corrigé, pas une
  régression ; `daily_budget_eur` doit être relu comme un vrai budget/jour.

## Limites assumées (hors périmètre de ce lot)

- Une escalade prouvée n'importe où dans la journée excuse tous les
  franchissements de seuil du jour — cohérent avec des métriques désormais
  journalières, mais grossier ; un ancrage temporel (escalade *après* le
  franchissement) reste ouvert.
- `loop_detected` reste contournable en variant un argument bidon, et un agent
  qui n'écrit aucune trace reste invisible : Alfred audite ce qui est émis.
- Le reste du pentest est planifié en lots séparés : disponibilité de
  l'auditeur (crash permanent sur trace malformée, `seen.json` indexé sur le nom
  de fichier), fuites (bypass de redaction via le blob JSON brut, en-tête
  `Authorization` conservé sur redirect cross-host, webhook Slack en clair en
  0644), intégrité du rendu (injection mrkdwn Slack, prompt injection via les
  event IDs, écrasement de preuves par `INSERT OR REPLACE`).

## Conséquences

- `src/alfred/mandate/engine.py` : `evaluate_trace`/`evaluate_day`/`evaluate`,
  `_check_cost_mismatch`, `_check_tool_not_allowed` fail-closed, coercition.
- `src/alfred/mandate/model.py` : `DeviationType.COST_MISMATCH`,
  `DeviationType.TOOL_UNIDENTIFIED`, `Mandate.escalation_tools`.
- `src/alfred/trace/cost.py` : `computed_cost_eur` / `declared_cost_eur`.
- `src/alfred/trace/ingest.py` : classification fail-closed.
- `src/alfred/report/build.py` : portée jour, ligne Escalations depuis les
  appels d'outil d'escalade.
- `src/alfred/mandate/yaml_io.py`, `lint.py` : champ + ERREUR de lint.
- Tests falsifiables : `test_mandate_engine.py`, `test_report_build.py`,
  `test_report_baseline.py`, `test_trace_cost.py`, `test_trace_ingest.py`,
  `test_mandate_yaml.py`, `test_mandate_lint.py`, `test_demo.py`.
- Docs : README (liste des déviations), `docs/integrate.md`, CHANGELOG.
- DoD inchangée : `pytest -q`, `ruff check .`, `mypy --strict src/` verts.

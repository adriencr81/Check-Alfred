# ADR 0011 — Évaluation du mandat au scope jour + arbitrages du plan prod

**Date** : 2026-07-19 · **Statut** : accepté ·
**Contexte** : `docs/plan-simplification-prod.md` (briques S1-S2, décisions §4).

## Problème

`daily_budget_eur` promettait un budget *quotidien*, mais `build_digest`
groupait les événements par `trace_id` et appelait `evaluate` trace par
trace : le budget était comparé au coût de chaque trace isolément. Une
journée de 10 traces à 1 € contre un budget de 5 € ne déclenchait rien.
L'ADR 0004 notait que l'agrégation « viendra avec le module report » — elle
n'était jamais venue. Même défaut pour les métriques d'escalade
(`budget_used`, `tool_error_rate`) et l'exemption `alfred.escalated`,
toutes calculées par trace.

S'y ajoutait une double définition du coût (B2) : le moteur ne lisait que
`gen_ai.usage.cost_eur` alors que le digest ajoutait un fallback
tokens × table de prix — la ligne Cost pouvait afficher une dépense que le
check budget ne voyait pas.

## Décisions

1. **Une seule définition du coût** : `alfred.cost.event_cost_eur`
   (attribut explicite, sinon fallback tokens, sinon 0), utilisée par le
   digest **et** par le moteur. Conséquence assumée : la dépense estimée
   par tokens compte désormais dans le budget.
2. **`evaluate(mandate, events)` prend un agent-jour entier** — le même
   scope que `build_digest`. Les checks par événement (`tool_not_allowed`,
   `forbidden_action`) sont indépendants du scope et inchangés. Les checks
   agrégés (`budget_exceeded`, `escalation_missed`) sont calculés sur le
   total du jour. `build_digest` ne groupe plus par trace — le groupement
   et sa boucle disparaissent.
3. **La frontière du jour est le jour calendaire UTC**, telle que déjà
   appliquée par `alfred.watch` (`start_time.date()` sur des datetimes
   UTC). Pas de gestion de fuseau en v0.1.
4. **L'exemption d'escalade est elle aussi au scope jour** : un événement
   `alfred.escalated` n'importe où dans la journée exempte les métriques
   agrégées du jour. C'est un affaiblissement assumé par rapport au
   per-trace (une escalade le matin couvre la journée) — cohérent avec un
   digest quotidien, et le cas inverse (escalade manquée malgré une
   escalade ailleurs) reste visible via la ligne Escalations.

## Arbitrages annexes du plan (décisions §4 du plan, actées ici)

- **Fichier corrompu (S3)** : marqué vu (quarantaine) + nommé dans la
  sortie d'`alfred watch` — pas de retentative à chaque exécution.
- **Format digest (S7)** : le rendu spécial « exactement 1 déviation »
  est supprimé au profit du format liste unique. Le gel du format
  (PLAN.md §5 B3) visait la stabilité inter-sinks, pas ce détail.
- **`narrate/` (B14)** : reste dans le paquet, **non branché** à la CLI en
  v0.1. L'exclure du wheel ajouterait de la complexité de packaging pour
  un bénéfice hypothétique (contraire à « simplicité d'abord ») ; le
  brancher ajouterait un appel réseau LLM au chemin critique de `watch`
  sans demande utilisateur. Statut documenté, décision re-examinée quand
  un chemin utilisateur l'exercera.

## Conséquences

- `test_reference_day_digest_snapshot` (journée type) reste valide : même
  résultat sous les deux sémantiques pour cette fixture — la différence
  n'apparaît que multi-traces, couverte par les nouveaux tests
  (`test_budget_aggregates_across_traces_of_the_same_day`,
  `test_escalation_exemption_is_day_scoped`).
- Le contrat documenté d'`evaluate` change (trace → agent-jour) ; tout
  appelant externe qui passait une trace seule obtient le même résultat
  qu'avant pour les checks par événement, et un scope plus honnête pour
  les checks agrégés.

# 0019 — Digest contextualisé par baseline glissante

**Date** : 2026-07-23 · **Statut** : Accepté · **Complète** : ADR 0005 (Brique 3), PLAN.md §13 F3

## Contexte

Le digest actuel (Brique 3) donne des chiffres bruts : « Coût 3,42 € », « Tasks
completed 47 ». Un manager ne sait pas si c'est *normal*. F3 (PLAN.md §13)
répond à la question « est-ce normal ? » en attachant à **chaque chiffre** sa
comparaison à une moyenne glissante : « Coût 3,42 € — +180 % vs moy. 7 j ⚠️ ».
C'est la version *légère* de la dérive de comportement (v0.3) : baseline
seulement, pas de bench rejoué.

Contrainte absolue (CLAUDE.md) : la comparaison « +180 % vs moy. 7 j » est une
**affirmation du rapport**, donc elle doit être *calculée depuis des events de
trace identifiables*. La moyenne est dérivée des events historiques ; la
`Baseline` porte les `event_id` qui l'ont produite — aucune moyenne auto-déclarée.

## Décisions

**1. La baseline décore une `Line`, elle ne crée pas de ligne.** Chaque `Line`
numérique gagne un champ optionnel `baseline: Baseline | None`. Une `Baseline`
porte `mean`, `window_days` (la fenêtre calendaire, 7), `sample_days` (les jours
*actifs* de la fenêtre) et `sources` (les `event_id` historiques qui la
prouvent). Invariant miroir de `Line`/`Deviation` : `Baseline.sources` est non
vide — une moyenne sans ancre est un bug, pas une donnée.

**2. Les trois lignes sont contextualisées.** PLAN.md §13 dit « chaque chiffre
gagne sa comparaison » : `tasks_completed`, `cost_eur` et `escalations` reçoivent
toutes la baseline. Traitement uniforme, aucun chiffre laissé sans jugement.

**3. Statistique : moyenne sur les jours *actifs* de la fenêtre de 7 jours.**
- Fenêtre : les 7 jours calendaires précédant le jour du digest (`BASELINE_WINDOW_DAYS = 7`),
  conforme à « moy. 7 j ».
- Un *jour actif* = un jour antérieur portant au moins un event. Un jour sans
  aucun event est un **échantillon manquant**, exclu de la moyenne — sinon un
  démarrage récent écrase la moyenne avec des faux zéros.
- Sur un jour actif, une métrique absente compte comme un **vrai 0** (0 escalade
  un jour où l'agent a travaillé est une observation, pas un trou). La moyenne
  d'une métrique = somme de ses valeurs quotidiennes (0 inclus) / nombre de jours
  actifs.
- La *même* fonction de calcul de ligne sert pour le jour courant et pour chaque
  jour historique — la baseline ne peut donc jamais diverger de la ligne qu'elle
  contextualise (même garantie que « budget et coût prix à l'identique », Brique 9).

**4. Seuil de significativité : ≥ 3 jours actifs.** En-dessous, aucune baseline
n'est attachée — une « moyenne » sur 1 jour bruyant afficherait des « +900 % »
trompeurs. Choix documenté ici plutôt que deviné en silence (CLAUDE.md).

**5. Marqueur ⚠️ : |Δ| ≥ 100 % vs la moyenne.** Un chiffre qui double (ou tombe
de moitié) est signalé ⚠️ ; en-dessous, la comparaison s'affiche sans alarme. Le
seuil est **symétrique** (au-dessus *et* en-dessous) : selon la métrique, un
effondrement compte autant qu'une flambée — le manager lit le signe (`+`/`-`).
Le seuil vit dans le rendu (`render._WARN_DELTA`), là où se décide le jugement
affiché, pas dans le modèle de données.
- La moyenne est toujours > 0 quand une baseline est attachée (elle exige ≥ 1
  event source, donc ≥ 1 valeur quotidienne > 0), donc le ratio Δ est toujours
  défini — pas de division par zéro à gérer au rendu.

**6. `build_digest` reste rétrocompatible.** Nouveau paramètre keyword optionnel
`history: Sequence[Sequence[TraceEvent]] = ()` (une liste d'events par jour
actif, déjà restreinte à la fenêtre par l'appelant). Vide → aucune baseline,
comportement Brique 3 inchangé, tous les tests existants restent verts. `demo`
(un seul jour synthétique) n'a pas d'historique et n'affiche donc pas de
baseline.

**7. Fenêtrage côté store par *date locale*.** `TraceStore.find_by_date_range(start, end)`
sélectionne les events dont la date de `start_time` est dans `[start, end]`, en
comparant le préfixe `YYYY-MM-DD` de l'ISO stocké (`substr(start_time,1,10)`).
Robuste au suffixe de fuseau, et cohérent avec le regroupement « par jour » de
`watch_once` (qui groupe déjà via `event.start_time.date()`). `watch_once` fournit
l'historique (fenêtre `[jour-7, jour-1]`, regroupée par date, jours actifs
seulement) ; le jour courant est exclu par la borne haute.

## Conséquences

- `src/alfred/report/model.py` : `Baseline` (frozen, `__post_init__` refuse
  `sources` vide) ; `Line` gagne `baseline: Baseline | None = None`.
- `src/alfred/report/build.py` : constantes `BASELINE_WINDOW_DAYS = 7`,
  `_MIN_BASELINE_SAMPLE_DAYS = 3` ; registre `_LINE_BUILDERS` (réutilisé pour le
  jour courant et l'historique) ; `_with_baseline(line, builder, history)` ;
  paramètre `history` sur `build_digest`.
- `src/alfred/trace/store.py` : `find_by_date_range(start, end)` (+ index sur
  `start_time`).
- `src/alfred/report/render.py` : `format_baseline(line) -> str | None`,
  constante `_WARN_DELTA`, appelée par `_render_line`.
- `src/alfred/deliver/slack.py` : la comparaison rejoint le champ de chaque
  compteur (réutilise `format_baseline`), pour que stdout et Slack restent
  identiques (docstring de `render`).
- `src/alfred/watch.py` : `watch_once` construit l'historique depuis le store et
  le passe à `build_digest`.
- Tests falsifiables : `tests/test_report_baseline.py` (moyenne sur jours actifs,
  vrai 0 compté, < 3 jours → pas de baseline, historique vide → pas de baseline,
  ancrage `event_id`, seuil ⚠️ à ±100 %, symétrie), `tests/test_trace_store.py`
  (fenêtre de dates, exclusion du jour courant et des jours hors fenêtre),
  `tests/test_report_render.py` (rendu de la comparaison, ⚠️ conditionnel),
  `tests/test_watch.py` (e2e : 4 jours ingérés → le digest du dernier jour porte
  une baseline coût ancrée aux jours antérieurs).
- `README.md` : exemple de digest mis à jour. `pyproject.toml` inchangé (aucune
  dépendance).

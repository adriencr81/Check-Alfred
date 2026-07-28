# 0018 — Bootstrap du mandat depuis les traces + `alfred mandate lint`

**Date** : 2026-07-22 · **Statut** : Accepté · **Complète** : ADR 0007, Brique 11

## Contexte

Écrire un `mandate.yaml` juste est la falaise d'onboarding d'Alfred : un nouvel
utilisateur doit deviner les noms exacts de ses outils (`gen_ai.tool.name`) et un
budget quotidien plausible *avant* d'avoir vu la moindre déviation. C'est le
frein direct au « test 5 minutes BYOA » (Brique 11, PLAN.md §6). Symétriquement,
un `mandate.yaml` qui *parse* n'est pas forcément *sain* : une métrique
d'escalade mal orthographiée (`escalate_when: ["tool_errors > 0.1"]`) charge sans
erreur et ne casse qu'à l'exécution, au fond de `engine._metric_value`.

F2 (PLAN.md §13) adresse les deux : proposer un mandat *observé* depuis les
traces, et valider un mandat *avant* qu'il ne serve.

## Décisions

**1. Un groupe de sous-commandes `alfred mandate`** (`lint`, `init`), comme
l'écrit PLAN.md §13. `alfred init` (scaffold projet complet) reste inchangé ;
`alfred mandate` regroupe les opérations qui portent sur le seul `mandate.yaml`.

**2. `alfred mandate init --from-traces DIR` *propose*, il n'écrit pas.** La
commande imprime le YAML suggéré sur stdout ; l'utilisateur relit puis redirige
(`… > mandate.yaml`). Fidèle au verbe « proposer » de PLAN.md §13, zéro risque
d'écrasement (contrairement à `alfred init` qui refuse d'écraser), et composable.
On ne réutilise que le nom de tool observé et le coût observé — les deux seuls
faits que la trace *contient*.

**3. Ce qui est proposé — et ce qui ne l'est pas.**
- `allowed_tools` : l'ensemble trié des `gen_ai.tool.name` distincts vus sur les
  spans `tool_call`. Un fait de trace.
- `agent` : le premier `gen_ai.agent.name` observé (sinon `--agent`, sinon la
  valeur par défaut `your-agent`, alignée sur `alfred init`).
- `daily_budget_eur` : le coût total du **jour le plus cher** observé, arrondi à
  l'euro supérieur (`math.ceil`), via `event_cost_eur` — la *même* fonction que
  le moteur de budget, donc jamais un centime d'écart. Faute de coût observable
  (aucun event chiffrable), on retombe sur le défaut de scaffold (5,00 €).
  **Aucune marge inventée** (CLAUDE.md : pas de seuil deviné, pas de flag pour un
  besoin hypothétique) — un commentaire dans l'en-tête YAML invite l'utilisateur
  à ajouter sa propre marge. `budget_exceeded` utilisant `>` strict, les traces
  qui ont servi à semer le budget ne le déclenchent pas.
- `forbidden_actions` / `escalate_when` : **vides**. Ce sont des règles de
  *politique*, pas des faits de comportement ; les inférer serait auto-déclaré,
  ce qui viole la règle produit absolue. Laissés vides, à écrire par l'humain.

**4. `alfred mandate lint [PATH]` — deux sévérités, un code de sortie.** `lint`
va au-delà de `load_mandate` (qui ne vérifie que le schéma) en ajoutant les
contrôles *sémantiques* qui, sinon, ne cassent qu'à l'exécution :
- **error** : YAML/schéma invalide (remonté par `MandateError`), fichier absent,
  et surtout **métrique d'escalade inconnue** — c'est le gain central : la seule
  erreur latente que `load_mandate` laisse passer et que `engine._metric_value`
  ne signale qu'au `watch`. La liste des métriques connues vit dans *une* source
  (`engine.KNOWN_ESCALATION_METRICS`), partagée par le moteur et le linter.
- **warning** : `allowed_tools` vide (tout appel d'outil lèvera
  `tool_not_allowed`), `daily_budget_eur <= 0` (toute dépense lèvera
  `budget_exceeded`). Signalés, mais non bloquants.

Code de sortie : **1 s'il existe au moins une *error*** (utilisable en CI /
pre-commit), **0 sinon** (les warnings s'impriment sans bloquer). Convention de
linter standard. Les errors partent sur stderr, les warnings sur stdout —
même posture « fail loudly » que le reste de la CLI.

**5. Aucune dépendance ajoutée.** Réutilise `load_mandate`, `dump_mandate`,
`event_cost_eur`, `ingest_otlp_file` et le modèle `Mandate` existants.

## Conséquences

- `src/alfred/mandate/engine.py` : ajout de la constante publique
  `KNOWN_ESCALATION_METRICS` (source unique), référencée par le message d'erreur
  de `_metric_value`.
- `src/alfred/mandate/lint.py` (nouveau) : `Severity`, `LintFinding`,
  `lint_mandate(path) -> list[LintFinding]`.
- `src/alfred/mandate/bootstrap.py` (nouveau) : `suggest_mandate(events, *, agent)
  -> Mandate`.
- `src/alfred/cli.py` : groupe `mandate` avec `lint` et `init --from-traces`.
- Tests falsifiables : `tests/test_mandate_lint.py` (mandat propre → zéro
  finding ; métrique inconnue → error ; `allowed_tools` vide → warning ; budget
  <= 0 → warning ; YAML cassé / fichier absent → error), `tests/test_mandate_bootstrap.py`
  (outils observés, budget = ceil du jour le plus cher, agent depuis la trace,
  repli défaut sans coût, politiques vides), `tests/test_cli.py`
  (`mandate lint` valide → code 0 ; métrique inconnue → code 1 ; `mandate init
  --from-traces` imprime un YAML re-parsable listant l'outil observé).
- `README.md` : les deux commandes ajoutées au Quickstart.
- `pyproject.toml` inchangé (aucune dépendance).

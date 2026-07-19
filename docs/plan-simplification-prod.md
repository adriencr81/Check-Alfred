# Plan — Simplification & amélioration vers un code prêt prod

**Date** : 2026-07-19 · **Périmètre** : tout `src/alfred/` + packaging + CI.
**Statut** : plan — aucune modification de code dans ce commit. Chaque brique
ci-dessous suivra le workflow imposé (plan → test falsifiable → code → preuve
pytest → un commit).

> Relation avec PLAN.md : ce document ne contredit aucune décision actée
> (D1-D5). Les deux points qui changent une sémantique documentée dans un ADR
> (S2, S6) exigeront leur propre ADR au moment de l'implémentation.

---

## 1. État des lieux vérifié

Commandes exécutées sur `ff47f1f` (main à jour) :

```
$ python -m pytest -q         → 118 passed
$ ruff check .                → All checks passed!
$ python -m mypy --strict src/ → Success: no issues found in 24 source files
```

La base est saine : petite (~1 500 lignes src), typée strictement, testée,
zéro dépendance lourde. Ce plan ne propose donc **pas de refonte** — il
corrige deux bugs de sémantique, durcit les points qui casseront en usage
réel, et supprime la duplication existante. Rien d'autre.

Note d'environnement : `mypy --strict src/` échoue si le binaire `mypy`
résolu par le PATH n'est pas celui de l'environnement du projet (constaté
ici avec un mypy pipx : faux positifs « stubs not installed »). D'où la
recommandation S8 d'invoquer `python -m mypy` partout (CI, CLAUDE.md,
pre-commit).

---

## 2. Problèmes identifiés

### P0 — Bugs de sémantique (le produit ment)

**B1. Le budget « quotidien » est évalué par trace, pas par jour.**
`report/build.py:94-101` (`_deviations`) groupe les événements par
`trace_id` et appelle `mandate/engine.evaluate` sur chaque trace isolément ;
`engine.py:109` (`_check_budget_exceeded`) compare donc `daily_budget_eur`
au coût **d'une seule trace**. Journée de 10 traces à 1 € contre un budget
de 5 € → aucune déviation alors que 10 € ont été dépensés. Même défaut pour
les métriques d'escalade `budget_used` et `tool_error_rate`
(`engine.py:127-144`), calculées par trace. L'ADR 0004 avait explicitement
noté que l'agrégation multi-trace « viendra avec le module report (B3) » —
elle n'est jamais venue. C'est une violation silencieuse de la promesse
produit : le digest affirme surveiller un budget quotidien qu'il ne
surveille pas.

**B2. Deux définitions du coût qui divergent.**
`engine._cost` (`engine.py:40-42`) ne lit que l'attribut
`gen_ai.usage.cost_eur`. `report/build._event_cost_eur`
(`build.py:41-56`) ajoute un fallback tokens × table de prix. Conséquence :
pour une trace sans `cost_eur` explicite, la ligne « Cost » du digest
affiche un montant pendant que le check budget voit 0 € et ne se déclenche
jamais. Deux vérités pour la même donnée dans le même rapport.

### P1 — Robustesse (ça cassera au premier usage réel)

**B3. Un fichier de trace corrompu empoisonne `alfred watch` pour toujours.**
`watch.py:64-69` : `ingest_otlp_file` lève sur JSON invalide
(`json.JSONDecodeError` ou `TraceIngestionError`), l'exception traverse
`watch_once` **avant** `_save_seen` — donc rien du batch n'est marqué vu, et
`cli._cmd_watch` (`cli.py:48-51`) ne rattrape aucune de ces exceptions :
traceback brut pour l'utilisateur, et le même crash à chaque exécution
suivante tant que le fichier reste dans le dossier. Un seul fichier malformé
bloque définitivement toute la surveillance.

**B4. La CLI n'attrape pas `DeliverError`.**
`cli.py:60` : si le webhook Slack est injoignable, traceback brut au lieu
d'un message d'erreur propre + code retour non nul.

**B5. `TraceStore.put_many` : un commit par événement, non atomique.**
`store.py:88-90` boucle sur `put`, qui commite à chaque insert. Lent
(N commits) et non atomique : un crash au milieu laisse un batch partiel
sans marqueur. Par ailleurs le store n'est pas un context manager, d'où le
`try/finally` manuel dans la CLI.

**B6. Idempotence de watch fondée sur le seul nom de fichier.**
`watch.py:59` : `p.name` comme clé de `seen.json`. Deux dossiers de traces
différents contenant `trace-1.json` sont confondus ; un fichier réécrit
avec du nouveau contenu n'est jamais réingéré.

**B7. Contrat non tenu dans `ingest`.**
La docstring de `ingest_otlp_json` (`ingest.py:82`) promet un `event_id`
« hex, lowercased » ; le code (`ingest.py:66`) ne normalise pas la casse.
Deux exporteurs OTLP écrivant le même spanId en casses différentes
produiraient deux anchors distincts.

### P2 — Packaging & livraison

**B8. `py.typed` absent.** Tout l'effort `mypy --strict` est invisible pour
les consommateurs du paquet : leurs mypy traiteront `alfred` comme non typé.

**B9. Métadonnées pyproject.** Les URLs pointent vers
`github.com/alfred-ai/alfred` (le repo réel est ailleurs — à aligner sur D3
ou corriger) ; la version est dupliquée entre `pyproject.toml` et
`alfred/__init__.py` (→ `[tool.hatch.version]` dynamique, une seule source).

**B10. Écarts CI.** La CI ne vérifie pas le format (`ruff format --check`) ;
elle type seulement `src/` alors que la config mypy locale couvre aussi
`tests/` ; `pytest-cov` est installé mais aucune couverture n'est mesurée ;
`mypy` y est invoqué nu (PATH-dépendant, cf. §1).

**B11. Webhook Slack en clair dans `config.toml`.** Un secret dans un
fichier de projet. Supporter la variable d'environnement
`ALFRED_SLACK_WEBHOOK_URL` (prioritaire sur le fichier) et documenter
l'ajout de `.alfred/` au `.gitignore` des projets utilisateurs.

### P2 — Simplifications (duplication et code mort)

**B12. `HTTPRequest`/`Transport`/`_urllib_transport` dupliqués** entre
`narrate/llm.py:79-104` et `deliver/slack.py:47-70` — deux copies quasi
identiques de la même politique HTTP. → module partagé `alfred/_http.py`
(~35 lignes supprimées, une seule politique d'erreur/timeout à maintenir).

**B13. `render._render_deviations` : cas spécial pour 1 déviation**
(`render.py:40-45`). Deux formats de sortie pour la même donnée. Le format
liste seul suffit et simplifie le code — mais le format est « gelé » par
PLAN.md §5, donc c'est une décision, pas un fait (cf. §4).

**B14. `narrate/` est du code mort côté produit.** La CLI ne l'importe
jamais : aucun chemin utilisateur n'exerce la NLG vérifiée. Le module est
testé et correct, mais livrer du code non branché dans un wheel v0.1 est un
choix à assumer explicitement (cf. §4) — pas une suppression silencieuse.

**B15. Micro-nettoyages optionnels.** `EscalationRule.breached` : chaîne de
`if` → dict d'opérateurs (`operator.gt`…). Table de prix
`_PRICING_EUR_PER_1K_TOKENS` GPT-only : documenter la limitation dans le
README plutôt que d'inventer un mécanisme de config (simplicité d'abord).

---

## 3. Briques d'exécution

Ordre choisi : corriger la vérité du rapport avant de polir. Une brique =
un commit, message anglais impératif, preuve pytest en fin de brique.

| # | Brique | Couvre | Test falsifiable (écrit d'abord) |
|---|---|---|---|
| S1 | **Coût unifié** : extraire `alfred/cost.py` (une seule fonction `event_cost_eur`), utilisée par `report/build` et `mandate/engine`. | B2 | Une trace sans `cost_eur` mais avec tokens+modèle connu → la ligne Cost du digest **et** le check budget voient le même montant. |
| S2 | **Scope jour** : scinder `evaluate` en checks par événement (tool_not_allowed, forbidden_action — inchangés) et checks agrégés (budget, escalade) évalués sur **tous** les événements du jour dans `build_digest`. ADR requis. | B1 | 3 traces × 2 € le même jour, budget 5 € → exactement une déviation `budget_exceeded` à 6 €. Contre-test : 3 × 1.5 € → aucune. |
| S3 | **Watch robuste** : ingestion par fichier avec capture d'erreur (fichier corrompu → signalé sur stderr, les autres fichiers sont ingérés, `seen.json` sauvé), CLI attrape `TraceIngestionError`/`DeliverError`/`ConfigError` → message propre + exit ≠ 0. | B3, B4 | Dossier avec 1 JSON corrompu + 2 valides → les 2 valides produisent un digest, le corrompu est nommé dans la sortie, la 2ᵉ exécution est un no-op. |
| S4 | **Store transactionnel** : `put_many` = une transaction (`executemany` + un commit) ; `TraceStore` context manager (`with TraceStore(...) as store:`), suppression du try/finally CLI. | B5 | Batch dont l'événement N est invalide → 0 ligne en base (rollback). |
| S5 | **HTTP partagé** : `alfred/_http.py` (HTTPRequest, Transport, transport urllib, garde http/https) ; `narrate` et `deliver` l'importent ; chaque module garde son type d'erreur. | B12 | Les tests existants de `narrate` et `slack` passent sans modification de leurs assertions. |
| S6 | **Idempotence + contrat ingest** : clé de `seen.json` = `nom:taille:mtime` ; lowercase de `spanId`/`traceId` à l'ingestion. ADR court (changement du format seen.json + de la casse des anchors). | B6, B7 | Fichier réécrit avec nouveau contenu → réingéré ; spanId `ABCD` dans le fichier → `event_id == "abcd"` partout. |
| S7 | **Secrets & rendu** : env var `ALFRED_SLACK_WEBHOOK_URL` prioritaire sur config.toml ; suppression du cas spécial 1-déviation dans `render` (si validé, cf. §4). | B11, B13 | Env var posée + config sans webhook → Slack livré ; digest à 1 déviation rendu au format liste. |
| S8 | **Packaging & CI** : `py.typed` + inclusion wheel ; version dynamique hatch ; URLs corrigées ; CI : `ruff format --check`, `python -m mypy` (config complète src+tests), `pytest --cov=alfred` en rapport (pas de seuil bloquant en v0.1). | B8, B9, B10 | `pip install` du wheel dans un venv vierge → `mypy` d'un script important `alfred` voit les types ; CI verte. |

Hors périmètre assumé (YAGNI v0.1, conforme « simplicité d'abord ») :
framework de logging, retries HTTP, autre base que SQLite, daemon watch,
mécanisme de config pour la table de prix, seuil de couverture bloquant.

---

## 4. Décisions à trancher avant d'implémenter

Conformément à « aucune supposition silencieuse », ces quatre points
attendent un arbitrage explicite :

1. **Sémantique du budget (S2)** : `daily_budget_eur` = jour calendaire
   **UTC** (frontière actuelle du groupement dans `watch`) ? Proposition :
   oui, documenté dans l'ADR — pas de gestion de fuseau en v0.1.
2. **Fichier corrompu (S3)** : marqué vu (quarantaine : signalé une fois,
   puis ignoré) ou retenté à chaque exécution ? Proposition : **marqué vu**
   + nommé dans la sortie — un fichier corrompu ne se répare pas tout seul,
   et le retenter à chaque cron spamme stderr.
3. **Format du digest (S7/B13)** : le format est gelé par PLAN.md §5 —
   a-t-on le droit de supprimer le rendu spécial « 1 déviation » ?
   Proposition : oui, le gel visait la stabilité inter-sinks, pas ce détail ;
   à défaut, S7 se fait sans ce point.
4. **`narrate/` (B14)** : brancher la NLG vérifiée dans le chemin de
   livraison derrière une section `[llm]` de config.toml, ou geler le module
   (exclu du wheel, réintégré quand un chemin utilisateur l'exerce) ?
   Proposition : **geler** — brancher un appel LLM dans `watch` ajoute une
   dépendance réseau au chemin critique sans demande utilisateur, et D5 est
   déjà démontrée par les tests du module.

---

## 5. Preuve de fin de plan

À la dernière brique, la définition de « prêt prod v0.1 » est :

- `python -m pytest -q` vert (tous les tests S1-S8 inclus) ;
- `ruff check . && ruff format --check . && python -m mypy` verts ;
- `alfred watch` survit à un dossier hostile (fichiers corrompus, Slack
  down) avec des messages propres et des codes retour corrects ;
- le digest ne peut plus affirmer un coût que le moteur de mandat ne voit
  pas, ni ignorer un dépassement de budget réparti sur plusieurs traces ;
- le wheel expose ses types et une seule source de version.

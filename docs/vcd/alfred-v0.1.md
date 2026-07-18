# VCD — Alfred v0.1 (léger, autonome)

**Date** : 2026-07-18 · **Auteur** : Claude Code (Brique 6)

## Ce que ce document est — et n'est pas

PLAN.md §5 Brique 6 demande que le repo Alfred soit « vérifié par la
méthodologie du harnais » (un repo de vérification RAG séparé). Ce repo
n'est pas dans le périmètre GitHub de la session qui a écrit ce document
— son template VCD exact n'a donc pas pu être appliqué à la lettre. Ce
qui suit est un **VCD léger et autonome** : un tableau qui relie chaque
invariant produit déclaré dans PLAN.md §3 et chaque contrat de brique
(§5) au(x) test(s) falsifiable(s) qui le prouve(nt) réellement dans ce
repo, plus le résultat d'une exécution réelle de la suite. Ce n'est pas
une déclaration de conformité à une méthodologie externe — voir
`docs/adr/0008-brique6-demo-launch-polish-design.md` décision 6.

## Exécution de référence

```
$ pip install -e ".[dev]"
$ pytest -q
112 passed in 0.51s
$ ruff check .
All checks passed!
$ mypy --strict src/
Success: no issues found in 24 source files
```

Commande exacte, date d'exécution 2026-07-18, sur la branche
`claude/brique-6-glenis`.

## Invariants produits (PLAN.md §3) → preuve

| Invariant | Preuve (test) | Fichier |
|---|---|---|
| `TraceEvent` est immuable, porte un `event_id` stable et unique | `test_event_is_immutable`, `test_events_with_same_id_are_equal`, `test_events_with_different_ids_are_not_equal`, `test_event_is_hashable` | `tests/test_trace_model.py` |
| Chaque `Line` d'un `Digest` a `sources: list[EventId]` non-vide | `test_line_requires_at_least_one_event_id` (modèle), `test_digest_every_line_has_sources` (bout-en-bout sur trace non-vide) | `tests/test_report_model.py`, `tests/test_report_build.py` |
| Chaque `event_id` cité dans un `Digest` existe réellement dans la trace source (pas de source fantôme) | `test_digest_sources_exist_in_store` | `tests/test_report_build.py` |
| `narrate` ne peut émettre un `NarratedDigest` que si les event IDs cités par phrase sont un sous-ensemble strict des `sources` de la ligne — **le test qui incarne la thèse du produit** | `test_narrated_digest_only_uses_source_events`, `test_narrate_raises_on_hallucinated_citation`, `test_narrate_raises_on_partial_hallucination`, `test_narrate_raises_on_missing_citation`, `test_narrate_aborts_whole_call_on_first_violation` | `tests/test_narrate_llm.py` |
| Chaque `Deviation` référence au moins un `event_id` qui la prouve | `test_deviation_requires_at_least_one_event_id`, `test_deviation_carries_its_event_ids`, `test_deviation_carries_event_ids_present_in_trace` | `tests/test_mandate_model.py`, `tests/test_mandate_engine.py` |

## Contrats de brique (PLAN.md §5) → preuve

| Brique | Objectif | Tests falsifiables clés | Statut |
|---|---|---|---|
| B1 — Trace store | OTLP JSON → `TraceEvent` → SQLite, retrouvable par ID | `test_ingest_returns_all_spans`, `test_ingest_preserves_span_id`, `test_ingest_extracts_gen_ai_usage`, `test_ingest_malformed_raises`, `test_put_then_get_roundtrip`, `test_find_by_trace_returns_all_events_of_a_trace` | ✅ |
| B2 — Mandat + déviations v0 | Mandat YAML → `list[Deviation]` typée, 4 types | un test par type + son miroir conforme dans `tests/test_mandate_engine.py` (12 tests), `test_mandate_yaml_roundtrip` | ✅ |
| B3 — Moteur de rapport | Traces + mandat + déviations → `Digest` | `test_digest_every_line_has_sources`, `test_digest_sources_exist_in_store`, `test_digest_cost_matches_sum`, `test_reference_day_digest_snapshot` | ✅ |
| B4 — Verified NLG | `Digest` → prose, zéro fait sans citation | `test_narrated_digest_only_uses_source_events` (voir tableau ci-dessus), `docs/verified_nlg.md` | ✅ |
| B5 — Livraison Slack + CLI | Webhook Block Kit, `alfred init`/`watch` | `test_slack_payload_is_valid_block_kit`, `test_watch_ingests_new_files_only`, `test_init_creates_config`, `test_end_to_end_trace_to_digest_to_slack_payload_without_network` | ✅ |
| B6 — `alfred demo` + polish | Agent factice → vraie trace → vrai digest, zéro dépendance | `test_build_demo_payload_ingests_to_real_events`, `test_demo_digest_is_credible`, `test_cli_demo_runs_fake_agent_and_prints_digest` | ✅ |

## Couverture par module (comptage réel des fonctions `test_*`)

| Module | Fichier(s) de test | Nombre de tests |
|---|---|---|
| `alfred.trace` | `test_trace_model.py`, `test_trace_ingest.py`, `test_trace_store.py` | 21 |
| `alfred.mandate` | `test_mandate_model.py`, `test_mandate_yaml.py`, `test_mandate_engine.py` | 21 |
| `alfred.report` | `test_report_model.py`, `test_report_build.py`, `test_report_render.py` | 22 |
| `alfred.narrate` | `test_narrate_llm.py` | 18 (dont un test paramétré sur 2 cas) |
| `alfred.deliver` | `test_deliver_stdout.py`, `test_deliver_slack.py` | 6 |
| `alfred.config` / `alfred.watch` | `test_config.py`, `test_watch.py` | 12 |
| `alfred.demo` | `test_demo.py` | 5 |
| `alfred.cli` | `test_cli.py` | 7 |
| **Total** | | **112** |

Compté via `pytest --collect-only -q`, pas par grep de `def test_*` — un
test paramétré compte pour ses N cas, pas pour 1 définition. Toute
divergence future entre ce tableau et `pytest --collect-only -q` signale
que ce document doit être régénéré.

## Limites connues (honnêtes, pas des trous cachés)

- Aucun test n'exerce un vrai réseau (LLM, Slack) — c'est un choix
  délibéré (`Transport`/`LLMClient` fakes), pas une lacune de couverture ;
  voir `docs/adr/0006-brique4-verified-nlg-design.md` et
  `docs/adr/0007-brique5-delivery-cli-design.md`.
- `alfred demo` n'est pas testé contre une installation `pip install
  alfred-ai` réelle — le paquet n'est pas encore publié sur PyPI (voir
  `docs/adr/0008-brique6-demo-launch-polish-design.md`).
- Le validateur Block Kit (`tests/_block_kit.py`) est un contrat maison
  dérivé de la documentation Slack, pas le validateur officiel Slack (qui
  n'existe pas sous forme de schéma téléchargeable) — documenté dans
  l'ADR 0007, décision 7.
- Ce VCD n'a pas été produit par (ni validé contre) la méthodologie du
  harnais RAG mentionnée dans PLAN.md §5 B6 — voir la section
  « Ce que ce document est » ci-dessus.

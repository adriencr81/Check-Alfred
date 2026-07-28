# VCD — Alfred v0.1 (léger, autonome)

**Version** : 3 · **Date** : 2026-07-28 · **Auteur** : Claude Code
(lancement PyPI, section finale) · **Version 2** : 2026-07-26 (régénération
pré-launch) · **Version 1** : 2026-07-18 (Brique 6)

## Ce que ce document est — et n'est pas

PLAN.md §5 Brique 6 demande que le repo Alfred soit « vérifié par la
méthodologie du harnais » (un repo de vérification RAG séparé). Ce repo n'est
pas dans le périmètre GitHub des sessions qui ont écrit ce document — son
template VCD exact n'a donc pas pu être appliqué à la lettre. Ce qui suit est un
**VCD léger et autonome** : un tableau qui relie chaque invariant produit
déclaré dans PLAN.md §3, chaque contrat de brique (§5, §12) et chaque feature
post-launch (§13) au(x) test(s) falsifiable(s) qui le prouve(nt) réellement dans
ce repo, plus le résultat d'une exécution réelle de la suite. Ce n'est pas une
déclaration de conformité à une méthodologie externe — voir
`docs/adr/0008-brique6-demo-launch-polish-design.md` décision 6.

**Pourquoi une version 2** : la version 1 attestait 112 tests et les briques
B1-B6. Depuis, le sprint BYOA (B7-B11), deux connecteurs natifs (B12, B13),
cinq features produit (F1-F4) et quatre rounds de durcissement (ADR 0023-0026)
sont mergés. Un VCD qui atteste un périmètre périmé n'atteste rien — c'est le
document qu'on ouvre pour vérifier une affirmation, pas un journal.

## Exécution de référence

Commandes exactes, exécutées le 2026-07-26 sur la branche
`claude/technical-checklist-launch-fizl21` (Python 3.11.15) :

```
$ python -m venv .venv && .venv/bin/pip install -e ".[dev]"
$ .venv/bin/python -m pytest -q
398 passed
$ .venv/bin/ruff check .
All checks passed!
$ .venv/bin/mypy --strict src/ tests/
Success: no issues found in 73 source files
```

Le `mypy --strict` couvre désormais `tests/` en plus de `src/` (38 fichiers pour
`src/` seul) — un argument positionnel écrasait le réglage `files` de
`pyproject.toml`, si bien que la suite de tests n'était en fait jamais
type-checkée.

**Vérification d'emballage** (ce que reçoit un utilisateur `pip install`, la
limite explicitement ouverte de la version 1 de ce document) :

```
$ .venv/bin/python -m build
Successfully built alfred_ai-0.1.0.tar.gz and alfred_ai-0.1.0-py3-none-any.whl
$ .venv/bin/twine check dist/*
PASSED (wheel), PASSED (sdist)
$ python -m venv /tmp/clean && /tmp/clean/bin/pip install dist/alfred_ai-0.1.0-py3-none-any.whl
$ /tmp/clean/bin/alfred demo        # hors du repo, sans source
Alfred · demo-bot · 2026-07-26 … Deviations (mandate): 1 [evt:demo-2-tool]
```

Le wheel s'installe dans un environnement vierge et `alfred demo` produit un
digest ancré sans le repo — ce qui restait non vérifié en version 1.

**Python 3.14 : confirmé par la CI, connecteurs compris.** La vérification
locale ne pouvait porter que sur le cœur — le seul interpréteur 3.14 que
l'environnement pouvait récupérer était un release candidate :

```
$ uv venv --python 3.14 && uv pip install -e . pytest
$ python -m pytest -q --ignore=tests/test_integration_langgraph.py \
                      --ignore=tests/test_integration_openai_agents.py
379 passed        # Python 3.14.0rc2 ; suite d'alors (393) moins les 14 connecteurs
```

Le doute portait sur les extras connecteurs, dont pydantic est une dépendance
transitive. Il est **levé** : sur un 3.14 final, le job `test (3.14)` de la CI
passe avec `pip install -e ".[dev]"`, `pytest -q` (les 14 tests connecteurs
inclus), `ruff` et `mypy --strict` verts
([run 30207988529](https://github.com/adriencr81/Check-Alfred/actions/runs/30207988529)).
L'échec local était bien un artefact du rc, comme l'ADR 0028 l'avançait — la
matrice a servi exactement à ce qu'on attendait d'elle.

**Chemin zéro-install** : `uvx --from <wheel local> alfred-ai demo` produit le
digest attendu, ce qui exerce la résolution du nom d'exécutable (l'alias
`alfred-ai` de l'ADR 0029). Le chemin `pipx` reste non vérifié — voir « Limites
connues ».

## Invariants produits (PLAN.md §3) → preuve

| Invariant | Preuve (test) | Fichier |
|---|---|---|
| `TraceEvent` est immuable, porte un `event_id` stable et unique | `test_event_is_immutable`, `test_events_with_same_id_are_equal`, `test_events_with_different_ids_are_not_equal`, `test_event_is_hashable` | `tests/test_trace_model.py` |
| Chaque `Line` d'un `Digest` a `sources: list[EventId]` non-vide | `test_line_requires_at_least_one_event_id` (modèle), `test_digest_every_line_has_sources` (bout-en-bout sur trace non-vide) | `tests/test_report_model.py`, `tests/test_report_build.py` |
| Chaque `event_id` cité dans un `Digest` existe réellement dans la trace source (pas de source fantôme) | `test_digest_sources_exist_in_store` | `tests/test_report_build.py` |
| `narrate` ne peut émettre un `NarratedDigest` que si les event IDs cités par phrase sont un sous-ensemble des `sources` de la ligne — **le test qui incarne la thèse du produit** | `test_narrated_digest_only_uses_source_events`, `test_narrate_raises_on_hallucinated_citation`, `test_narrate_raises_on_partial_hallucination`, `test_narrate_raises_on_missing_citation`, `test_narrate_aborts_whole_call_on_first_violation` | `tests/test_narrate_llm.py` |
| Une phrase narrée doit porter **la valeur** de la ligne qu'elle rapporte, pas seulement une citation valide (ADR 0026) | `test_sentence_without_its_value_is_rejected`, `test_sentence_carrying_its_value_is_accepted` | `tests/test_narrate_llm.py` |
| Chaque `Deviation` référence au moins un `event_id` qui la prouve | `test_deviation_requires_at_least_one_event_id`, `test_deviation_carries_its_event_ids`, `test_deviation_carries_event_ids_present_in_trace` | `tests/test_mandate_model.py`, `tests/test_mandate_engine.py` |
| Aucune affirmation du rapport ne repose sur ce que l'agent déclare sur lui-même (ADR 0023) | `test_token_price_wins_over_the_declared_cost`, `test_self_declared_escalation_attribute_no_longer_suppresses_the_deviation` | `tests/test_trace_cost.py`, `tests/test_mandate_engine.py` |

## Contrats de brique (PLAN.md §5, §12) → preuve

| Brique | Objectif | Tests falsifiables clés | Statut |
|---|---|---|---|
| B1 — Trace store | OTLP JSON → `TraceEvent` → SQLite, retrouvable par ID | `test_ingest_returns_all_spans`, `test_ingest_preserves_span_id`, `test_ingest_extracts_gen_ai_usage`, `test_ingest_malformed_raises`, `test_put_then_get_roundtrip`, `test_find_by_trace_returns_all_events_of_a_trace` | ✅ |
| B2 — Mandat + déviations v0 | Mandat YAML → `list[Deviation]` typée | un test par type + son miroir conforme dans `tests/test_mandate_engine.py` (32 tests), `test_mandate_yaml_roundtrip` | ✅ |
| B3 — Moteur de rapport | Traces + mandat + déviations → `Digest` | `test_digest_every_line_has_sources`, `test_digest_sources_exist_in_store`, `test_digest_cost_matches_sum`, `test_reference_day_digest_snapshot` | ✅ |
| B4 — Verified NLG | `Digest` → prose, zéro fait sans citation | `test_narrated_digest_only_uses_source_events` (voir tableau ci-dessus), `docs/verified_nlg.md` | ✅ |
| B5 — Livraison Slack + CLI | Webhook Block Kit, `alfred init`/`watch` | `test_slack_payload_is_valid_block_kit`, `test_watch_ingests_new_files_only`, `test_init_creates_config`, `test_end_to_end_trace_to_digest_to_slack_payload_without_network` | ✅ |
| B6 — `alfred demo` + polish | Agent factice → vraie trace → vrai digest, zéro dépendance | `test_build_demo_payload_ingests_to_real_events`, `test_demo_digest_is_credible`, `test_cli_demo_runs_fake_agent_and_prints_digest` | ✅ |
| B7 — Premier agent réel vérifié | Boucle d'outils Claude sans framework → déviation attrapée sur run non scripté | `tests/test_example_refund_bot.py` (6 tests, client LLM scripté) + **run réel** du 2026-07-20 (ADR 0013) | ✅ |
| B8 — SDK `alfred.instrument` | Une boucle quelconque s'instrumente en ~10 lignes | `test_instrumented_loop_trace_ingests`, `test_tool_arguments_flattened`, `test_tool_error_recorded`, `test_usage_propagated`, `test_digest_from_instrumented_trace_anchored`, `test_call_outside_session_raises` | ✅ |
| B9 — Mandat générique + coût depuis les tokens | Règles sur n'importe quel outil/argument ; budget sans `cost_eur` | `test_structured_forbidden_rule_triggers` + son miroir, `test_structured_rule_yaml_roundtrip`, `test_budget_from_tokens_without_cost_attr`, `tests/test_trace_cost.py` (20 tests) | ✅ |
| B10 — Ingestion du monde réel | NDJSON du file exporter Collector + semconv standard | `test_ingest_ndjson_lines`, `test_status_code_error_maps_to_tool_error`, `test_tool_call_arguments_json_parsed`, `test_malformed_ndjson_raises`, et les deux tests de non-écrasement des clés natives | ✅ |
| B11 — Onboarding + test 5 minutes BYOA | Agent externe jouet, zéro clé, digest ancré | `test_run_emits_ingestible_otlp`, `test_digest_lines_are_all_anchored`, `test_over_cap_approval_yields_forbidden_action` + vérification live (ci-dessous) | ✅ |
| B12 — Connecteur natif LangGraph | Un callback handler, aucune instrumentation manuelle | `tests/test_integration_langgraph.py` (7 tests : vrai `StateGraph` + fake chat model, zéro réseau) | ✅ |
| B13 — Connecteur natif OpenAI Agents SDK | Un tracing processor, aucune instrumentation manuelle | `tests/test_integration_openai_agents.py` (7 tests : vrai `Runner.run_sync` + client factice sur `MockTransport`) | ✅ |

## Features post-launch (PLAN.md §13) → preuve

| # | Feature | Tests falsifiables clés | ADR |
|---|---|---|---|
| F1 | Alertes de déviation en temps réel | `test_alert_payload_has_alert_header_and_deviation_section`, `test_alert_payload_evidence_lists_deviation_event_ids`, `test_alert_payload_is_valid_block_kit`, `test_build_alert_payload_requires_a_deviation` | 0017 |
| F2 | Bootstrap du mandat + `mandate lint` | `tests/test_mandate_bootstrap.py` (6 tests, dont `test_suggest_mandate_leaves_policy_fields_empty`), `tests/test_mandate_lint.py` (10 tests) | 0018 |
| F3 | Digest contextualisé par baseline glissante | `tests/test_report_baseline.py` (8 tests), `test_watch_attaches_rolling_baseline_from_store_history` | 0019 |
| F4 | Rapport HTML statique partageable | `tests/test_report_html.py` (10 tests, dont `test_every_source_link_resolves_to_an_evidence_anchor` et `test_render_html_is_a_self_contained_document`) | 0020 |
| F5 | Connecteurs natifs (moitié OpenAI Agents SDK) | voir B13 ci-dessus ; **CrewAI reste à livrer** (v0.2) | 0021 |
| — | Redaction PII/secrets | `tests/test_trace_redact.py` (14 tests, dont `test_redacted_value_absent_from_store`) | 0022 |
| — | Digest quotidien non-assisté (`schedule --github-actions`) | `tests/test_schedule.py` (17 tests, dont `test_github_actions_workflow_quotes_a_hostile_traces_dir`) | 0027 |

## Rounds de durcissement → preuve

Le modèle de menace traite **l'agent audité comme l'adversaire** : c'est lui qui
écrit la trace qu'Alfred lit.

| Round | Ce qui était cassé | Preuve du correctif | ADR |
|---|---|---|---|
| Contrôles de mandat | Budget évalué par trace (dix tâches sous le cap = dix fois le cap) ; coût auto-déclaré écrasant le prix calculé ; escalade prouvée par un attribut que l'agent écrit ; span sans `gen_ai.tool.name` échappant à tout contrôle ; seuil contourné en passant `"9999"` en string | `test_cost_mismatch_accumulates_over_the_day`, `test_token_price_wins_over_the_declared_cost`, `test_self_declared_escalation_attribute_no_longer_suppresses_the_deviation`, `test_escalation_can_never_be_proven_without_declared_escalation_tools`, `test_tool_call_without_a_name_is_reported`, `test_forbidden_action_threshold_detected_on_a_numeric_string`, `test_forbidden_action_reports_an_argument_it_cannot_compare` | 0023 |
| Disponibilité de l'auditeur | Un span malformé tuait `alfred watch` définitivement ; `seen.json` indexé par nom laissait un fichier réécrit non audité ; un webhook injoignable terminait la supervision | `test_watch_quarantines_an_unparsable_file_and_still_delivers_the_rest`, `test_watch_keeps_reporting_a_quarantined_file_on_later_passes`, `test_watch_reingests_a_file_whose_content_changed`, `test_watch_adopts_a_v1_seen_file_without_reingesting`, `test_watch_loop_runs_max_passes_and_sleeps_between_them` | 0024 |
| Confinement des fuites | PII déclarée stockée en clair dans le blob `gen_ai.tool.call.arguments` ; masque non salé réversible par dictionnaire ; clé API LLM survivant à une redirection cross-host ; webhook Slack world-readable | `test_redacted_value_masked_inside_the_raw_arguments_blob`, `test_redacted_value_masked_inside_a_nested_blob`, `test_redaction_key_is_created_private_and_reused`, `test_redaction_tokens_differ_between_projects`, `test_redirect_to_another_host_is_refused`, `test_post_rejects_cleartext_to_a_remote_host`, `test_post_error_never_echoes_the_url_path`, `test_config_file_is_owner_only`, `test_seen_state_and_store_are_owner_only` | 0025 |
| Intégrité rapport & preuve | Faux contenu forgé dans un vrai digest (markup Slack, `<!channel>`, `\r` en stdout) ; `spanId` non contraint atteignant le prompt de narration ; preuve stockée réécrite après diffusion | `test_deviation_message_cannot_forge_slack_markup`, `test_deviation_message_is_truncated`, `test_alert_payload_escapes_the_same_way`, `test_render_strips_control_characters_from_trace_text`, `test_render_html_escapes_untrusted_text`, `test_unsafe_span_id_is_rejected`, `test_unsafe_trace_id_is_rejected`, `test_conflicting_event_does_not_overwrite_the_stored_one`, `test_identical_re_put_is_not_a_conflict`, `test_watch_reports_an_event_that_tries_to_overwrite_stored_evidence` | 0026 |

## Couverture par module (comptage réel)

| Module | Fichier(s) de test | Nombre de tests |
|---|---|---|
| `alfred.trace` | `test_trace_model.py` (4), `test_trace_ingest.py` (36), `test_trace_store.py` (14), `test_trace_cost.py` (20), `test_trace_redact.py` (14) | 88 |
| `alfred.mandate` | `test_mandate_model.py` (4), `test_mandate_yaml.py` (14), `test_mandate_engine.py` (32), `test_mandate_bootstrap.py` (6), `test_mandate_lint.py` (10) | 66 |
| `alfred.report` | `test_report_model.py` (6), `test_report_build.py` (17), `test_report_render.py` (15), `test_report_baseline.py` (8), `test_report_html.py` (10) | 56 |
| `alfred.narrate` | `test_narrate_llm.py` (20), `test_narrate_render.py` (1) | 21 |
| `alfred.deliver` / `alfred._http` | `test_deliver_slack.py` (17), `test_deliver_stdout.py` (1), `test_http.py` (8) | 26 |
| `alfred.config` / `alfred.watch` | `test_config.py` (21), `test_watch.py` (16) | 37 |
| `alfred.instrument` | `test_instrument.py` | 7 |
| `alfred.integrations` | `test_integration_langgraph.py` (7), `test_integration_openai_agents.py` (7) | 14 |
| `alfred.demo` | `test_demo.py` | 5 |
| `alfred.cli` / `alfred.schedule` | `test_cli.py` (46), `test_schedule.py` (17) | 63 |
| `examples/agents` | `test_example_refund_bot.py` (6), `test_example_minimal.py` (3) | 9 |
| Emballage / landing | `test_version.py` (2), `test_docs_site.py` (4) | 6 |
| **Total** | | **398** |

Compté via `pytest --collect-only -q`, pas par grep de `def test_*` — un test
paramétré compte pour ses N cas, pas pour 1 définition. Toute divergence future
entre ce tableau et `pytest --collect-only -q` signale que ce document doit être
régénéré.

La dernière ligne ne teste pas du code applicatif mais des **faits
d'emballage** : la cohérence des versions, les deux scripts console (sans quoi
`uvx alfred-ai demo` échoue sur un paquet correctement installé), et le fait que
la landing ne publie ni le plan de croissance ni les ADR. Chacun est une panne
que seul un nouvel utilisateur — ou personne — rencontrerait (ADR 0029).

## Limites connues (honnêtes, pas des trous cachés)

- Aucun test n'exerce un vrai réseau (LLM, Slack) — c'est un choix délibéré
  (`Transport`/`LLMClient` fakes), pas une lacune de couverture ; voir
  `docs/adr/0006-brique4-verified-nlg-design.md` et
  `docs/adr/0007-brique5-delivery-cli-design.md`.
- **Le chemin `pipx run` n'est pas vérifié.** `uvx` l'est (voir « Exécution de
  référence »), et les deux lanceurs résolvent l'exécutable de la même façon,
  mais le binaire `pipx` de l'environnement de vérification refuse de démarrer
  contre l'`uv` installé, quel que soit le backend. L'affirmation reste à
  confirmer sur une machine où `pipx` tourne (ADR 0029).
- Le validateur Block Kit (`tests/_block_kit.py`) est un contrat maison dérivé
  de la documentation Slack, pas le validateur officiel Slack (qui n'existe pas
  sous forme de schéma téléchargeable) — documenté dans l'ADR 0007, décision 7.
- `alfred demo` est désormais vérifié depuis un wheel installé dans un
  environnement vierge (voir « Vérification d'emballage »), mais **pas** depuis
  un `pip install alfred-ai` réel : le paquet n'est pas encore publié. La
  chaîne de publication (`release.yml`, Trusted Publishing OIDC) n'a jamais été
  exécutée — zéro run, zéro tag.
- Alfred ne voit que ce que la trace enregistre. Un agent qui s'échappe de son
  instrumentation, ou un outil qui renvoie du faux avec un statut de succès, ne
  laisse aucun signal — limite documentée dans `SECURITY.md`, pas un trou de
  couverture.
- Les modes de fichiers owner-only sont un plancher POSIX ; sur Windows la vraie
  protection vient des ACL NTFS (`src/alfred/_fs.py`).
- Ce VCD n'a pas été produit par (ni validé contre) la méthodologie du harnais
  RAG mentionnée dans PLAN.md §5 B6 — voir la section « Ce que ce document
  est » ci-dessus.

## Brique 11 — vérification live (2026-07-21, conservée)

Le sprint S1 « Bring Your Own Agent » (PLAN.md §12, ADR 0013, briques 8-11) est
mergé sur `main`. À cette date la suite complète était verte à 151 tests
(`mypy --strict src/` : 27 fichiers).

Le « test 5 minutes BYOA » de la brique 11 (`examples/agents/minimal/`) a été
rejoué en conditions réelles, hors CI : `expense-bot` (aucun LLM, aucune clé
API) exécuté, sa trace ingérée par `alfred watch` dans un projet isolé, digest
produit et **livré dans Slack** (`#tous-alfred-demo`, Block Kit natif —
ADR 0012) via le webhook de démo existant :

```
Alfred · expense-bot · 2026-07-21

Tasks completed:          3   [evt:5ff68d0c…, 1481d192…, d81a8f46…]
Deviations (mandate):          1   [evt:b92e06a2…] — forbidden_action: forbidden action
'approve_expense_above_100_eur': approve_expense called with amount_eur=250.0 > 100.0
```

## Chaîne complète rejouée (2026-07-26)

Le même chemin BYOA rejoué à la régénération de ce document, depuis le wheel et
sur un projet neuf — nouveaux event IDs, donc nouveau run, aucun chiffre
recopié :

```
$ python -m minimal.agent
Trace written to traces/expense-bot-20260726-144350-d5a5.json
$ alfred watch traces/
Alfred · expense-bot · 2026-07-26

Tasks completed:               3   [evt:b0371725…, cfada657…, 9a60ef3f…]
Deviations (mandate):          1   [evt:ca93eee4…] — forbidden_action: forbidden action
'approve_expense_above_100_eur': approve_expense called with amount_eur=250.0 > 100.0

$ alfred report traces/ --html --out reports/
alfred report: wrote reports/alfred-expense-bot-2026-07-26.html
$ alfred schedule traces/ --at 09:00 --github-actions
name: Alfred daily digest        # workflow committable, webhook depuis un secret
```

Confirme la DoD de la brique 11 (un inconnu voit un digest ancré, avec une
déviation attrapée, sans réseau ni clé API, en moins de 5 minutes) et les DoD
F4 et ADR 0027 sur le même run.

## Lancement PyPI (2026-07-28)

Alfred est public : `pip install alfred-ai` installe la **0.1.1** depuis le
vrai index. Vérifié le soir même, depuis un venv vierge sans aucun accès au
repo :

```
$ pip install alfred-ai
$ alfred --version
alfred 0.1.1
$ alfred demo
Alfred · demo-bot · 2026-07-28

Tasks completed:               3   [evt:demo-1-task, demo-2-task, demo-3-task]
…
```

L'API PyPI confirme deux versions publiées le 2026-07-28 : `0.1.0` et `0.1.1`,
la 0.1.1 servie par défaut. **La 0.1.0 est un accident consigné** : publiée
manuellement depuis une copie locale restée au niveau de la brique 11 (avant
les PRs #19-49), elle est immuable et supersédée le jour même — voir la
section « About 0.1.0 » du CHANGELOG. Le tag `v0.1.0` pointe volontairement
sur le snapshot réellement publié, pas sur main.

La release 0.1.1 (tag `v0.1.1`, commit `71a8268`) a ajouté par rapport au main
pré-launch :

- **Fix Windows réel attrapé par le smoke test pré-publication** : la sortie
  redirigée (`alfred --help`, `alfred demo > out.txt`, CI) encodait en cp1252
  et crashait en `UnicodeEncodeError` sur la flèche `→` du texte d'aide. Le
  CLI force désormais stdout/stderr en UTF-8 ; test falsifiable
  `test_cli_output_survives_cp1252_stdout` (subprocess en `PYTHONIOENCODING=
  cp1252`), écrit rouge avant le fix, vert après.
- Liens README absolus (la page PyPI ne résout pas les chemins relatifs).
- 3 tests de permissions POSIX marqués skip sur Windows, où `chmod` ne sait
  pas exprimer owner-only — le CI ubuntu continue de les exécuter.

Exécution de référence au tag `v0.1.1` (Windows 11, Python 3.13.5) :

```
$ python -m pytest
401 passed, 3 skipped in 17.70s
$ python -m ruff check .
All checks passed!
$ python -m mypy
Success: no issues found in 73 source files
```

Le même jour, les deux premières PRs externes ont été revues et mergées :
**#53** (pricing DeepSeek, ferme #50 — prix sourcé, conversion recalculée à la
main, tests calqués sur le pattern existant) et **#54** (mandat d'exemple
`support-triage-bot.yaml` — chargé par le loader, 0 finding à
`alfred mandate lint`). Vérification pré-merge en worktree local, les deux PRs
mergées ensemble sur main : `403 passed, 3 skipped`, ruff et mypy propres —
équivalent du CI, dont les runs de forks attendaient une approbation manuelle.

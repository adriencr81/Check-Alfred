# 0008 — Conception de `alfred demo` + polish de lancement (Brique 6)

**Date** : 2026-07-18 · **Statut** : Accepté · **Signé** : Claude Code (Brique 6)

## Contexte

PLAN.md §5 Brique 6 fixe l'objectif (`alfred demo` lance un agent factice
instrumenté, génère une vraie trace, produit un vrai digest, zéro
dépendance externe) et une liste de critères de qualité repo (README, CI,
CHANGELOG, CONTRIBUTING, templates d'issues, tag PyPI, VCD). Plusieurs de
ces points dépassent ce qu'une session de code peut exécuter (publication
PyPI, tag + push, GIF réel, ouverture d'issues publiques) — deux points
ont été tranchés avec l'utilisateur avant implémentation (discipline
CLAUDE.md : « ne pas deviner, demander »), consignés ci-dessous.

## Décisions

**1. Périmètre de la session — code et artefacts de repo uniquement.**
Décision utilisateur explicite. Cette brique livre : `alfred demo` +
agent factice + tests, CI GitHub Actions (tests + CodeQL), CHANGELOG,
CONTRIBUTING, templates d'issues, ce document, `docs/vcd/alfred-v0.1.md`,
et une mise à jour chirurgicale du README. **Restent hors périmètre**,
laissés comme actions manuelles à l'utilisateur (voir README ou message
de fin de tâche pour la checklist) : publication `alfred-ai` sur PyPI,
tag `v0.1.0` + push, enregistrement du vrai GIF de démo, ouverture des
3 issues « good first issue », réservation du domaine/org GitHub
`alfred-ai`. Ce sont des actions à portée publique ou nécessitant des
identifiants que CLAUDE.md et les instructions d'exécution générales
placent hors de portée d'une prise de décision silencieuse par l'agent.

**2. `alfred demo` dogfoode le pipeline d'ingestion réel plutôt que de
construire des `TraceEvent` à la main.** `alfred.demo.fake_agent.
build_demo_payload` construit un payload OTLP JSON (même forme que
`tests/fixtures/otlp_sample.json`), passé à
`alfred.trace.ingest.ingest_otlp_json` — le même point d'entrée
qu'`alfred watch` utilise sur un fichier réel. C'est ce qui rend la
formulation de PLAN.md (« génère une vraie trace ») littéralement vraie :
la démo traverse la même frontière d'ingestion que n'importe quelle
trace OTLP réelle, elle n'emprunte pas de raccourci interne.

**3. Pas de persistance pour `demo`.** Contrairement à `alfred watch`,
`alfred demo` n'ouvre pas de `TraceStore` SQLite et n'écrit rien sur
disque. L'objectif de B6 est l'évaluation zéro-friction du produit
(« zéro dépendance externe pour évaluer le produit ») — chaque
invocation est indépendante et rejouable sans état à nettoyer.

**4. Pas d'appel à `narrate` (LLM) dans `demo`.** Le texte de PLAN.md §5
B6 ne mentionne que trace → digest, pas de prose narrée ; brancher
`narrate` exigerait une clé API, ce qui contredirait « zéro dépendance
externe ». `alfred demo` s'arrête donc au `Digest` rendu en texte
(`alfred.report.render` via `alfred.deliver.stdout`), comme le fait déjà
`alfred watch` pour sa sortie stdout.

**5. Scénario de démo choisi délibérément pour être « crédible » en
moins de 5 minutes (DoD de B6).** Trois tâches indépendantes
(`onboard_customer`, `handle_support_ticket`, `escalate_complex_case`),
chacune un `agent_task` + un appel `chat` (avec `gen_ai.usage.cost_eur`
explicite pour un total non-arrondi à zéro) + un `execute_tool`. Le
mandat de démo (`allowed_tools={"send_email"}`) n'autorise pas le
`read_pii` appelé par la deuxième tâche — écho volontaire de l'exemple
`read_pii` déjà utilisé dans PLAN.md §5 B3 et le README, pour que la
première chose qu'un nouvel utilisateur voie soit exactement la
déviation que la documentation promet. La troisième tâche porte
`alfred.escalated=true` pour peupler la ligne Escalations sans déclencher
`escalation_missed` (le mandat de démo ne définit aucun `escalate_when`,
donc ce chemin n'a pas besoin d'être exercé ici — il l'est déjà par
`tests/test_mandate_engine.py`).

**6. `docs/vcd/alfred-v0.1.md` est un document léger et autonome, pas la
méthodologie exacte du « harnais RAG ».** Décision utilisateur explicite.
PLAN.md §5 B6 demande que le repo Alfred soit « vérifié par la
méthodologie du harnais » — un repo séparé, hors du périmètre GitHub de
cette session. Le VCD produit ici fait le lien invariant produit
(PLAN.md §3) → test(s) qui le prouvent → fichier, construit uniquement à
partir des fichiers de test réellement présents dans ce repo et d'une
exécution réelle de `pytest -q`. Documenté honnêtement comme tel : si la
méthodologie du harnais a des exigences supplémentaires (structure de
preuve spécifique, format de rapport), ce document ne les couvre pas.

## Conséquences

- Nouveaux fichiers : `src/alfred/demo/{__init__.py,fake_agent.py}`,
  `tests/test_demo.py`, `.github/workflows/{ci.yml,codeql.yml}`,
  `.github/ISSUE_TEMPLATE/{bug_report.md,feature_request.md}`,
  `CHANGELOG.md`, `CONTRIBUTING.md`, ce document,
  `docs/vcd/alfred-v0.1.md`.
- `src/alfred/cli.py` : `_cmd_demo_stub` remplacé par `_cmd_demo`
  (branche réellement `build_demo_payload` → `ingest_otlp_json` →
  `build_digest` → `stdout.deliver`) ; `demo_parser` gagne `--agent`
  (défaut `demo-bot`).
- `tests/test_cli.py::test_cli_demo_is_still_a_stub` remplacé par
  `test_cli_demo_runs_fake_agent_and_prints_digest`.
- `pyproject.toml` inchangé : aucune nouvelle dépendance de production ni
  de dev pour cette brique.
- `pytest -q` (112 tests), `ruff check .` et `mypy --strict src/` verts
  sur tout le repo après cette brique.
- Checklist explicitement laissée à l'utilisateur (voir décision 1) :
  publication PyPI, tag + push, GIF réel, issues « good first issue »,
  réservation domaine/org.

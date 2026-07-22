# Alfred — Plan opérationnel

> Source de vérité unique. Toute décision qui contredit ce document doit
> soit modifier ce document, soit être documentée dans un ADR daté sous
> `docs/adr/`. Pas de plan parallèle en tête ou en Notion.

**Version** : 1.3 · **Date** : 2026-07-21 · **Cible produit** : v0.1 publique le **4 août 2026** (J+20).
**Cible fondateur** : candidature YC **déposée le 2026-07-18** — traction démontrable avant la réponse YC.

> Révision v1.1 (2026-07-18, ADR 0009) : les 6 briques §5 sont livrées à
> J+3 (112 tests, mypy --strict, CI + CodeQL verts). D2 est supersédée
> (candidature YC déposée), le launch avance du 30 août au 4 août, et un
> sprint S0 « tout ce qui est public » remplace §11. Voir
> `docs/adr/0009-yc-application-submitted-replan-v1-1.md`.

> Révision v1.2 (2026-07-20, ADR 0013) : **le run réel B7 est exécuté** —
> déviation `forbidden_action` attrapée sur un run non scripté, digest
> livré dans Slack. Le verrou ADR 0010 est levé. Un sprint S1 « Bring Your
> Own Agent » (§12, Briques 8-11) rend le produit utilisable par un dev
> externe avec *ses* agents ; B8 + B11 sont sur le chemin critique du
> launch (maintenu au 4 août s'ils sont verts au 1er août, sinon 11 août).
> Voir `docs/adr/0013-byoa-bring-your-own-agent-plan.md`.

> Révision v1.3 (2026-07-21, ADR 0014) : le **connecteur natif LangGraph**
> (§12, Brique 12) est avancé sur demande produit, en anticipé sur la v0.2 où
> il était backlogué (§10, « priorisés par les issues »). Écart de
> séquencement assumé et cloisonné : un `BaseCallbackHandler`
> (`alfred.integrations.langgraph`) derrière l'extra optionnel `[langgraph]`,
> pilotant les context managers d'`AgentTracer` — le cœur garde sa seule
> dépendance `pyyaml`. Les autres connecteurs (CrewAI, OpenAI) et non-objectifs
> du backlog §10 restent en v0.2+. Voir
> `docs/adr/0014-langgraph-native-connector.md`.

---

## 1. Décisions actées (verrouillé)

| # | Décision | Impact |
|---|---|---|
| D1 | **Séquencement hybride RAG→Alfred** : finir la Brique 6 du harnais RAG (en cours). Geler B7-B9 en backlog. Attaquer Alfred immédiatement après. | Launch Alfred déplacé de J+150 à J+45 (~30 août 2026). |
| D2 | ~~YC : cible unique = candidature sérieuse 2027. Pas de candidature-exercice Fall 2026.~~ **Supersédée (ADR 0009)** : candidature déposée le 2026-07-18. Le plan est calé sur les événements YC (invitation à interview), pas sur des dates de batch. | Piste parallèle « YC-readiness » (vidéo 1 min, screencast démo, why-now, suivi métriques hebdo). |
| D3 | **Nom paquet PyPI = `alfred-ai`**, nom import = `alfred`, org GitHub = `alfred-ai`. | Ligne 1 du README. À réserver dans la semaine. |
| D4 | **Licence Apache 2.0** pour le paquet open-source, moteur de mandat avancé closed-source (open-core assumé dès le README). | Ligne 2 du README. |
| D5 | **Règle produit absolue** : chaque affirmation d'un rapport est ancrée sur un event ID de la trace. Le LLM ne fait que la mise en langage. | Encodée dans CLAUDE.md et testée par un test dédié (B4). |

**Ce que la décision D1 signifie concrètement pour le harnais RAG** : B6 se finit proprement (test de bout en bout, commit, tag `v1.0`), README à jour, issues restantes étiquetées `v1.1-later`. **B7-B9 basculent en backlog documenté** (`BACKLOG_RAG.md` dans le repo du harnais, pas ici). Le leaderboard (B9) reviendra comme *machine à contenu marketing d'Alfred* — pas comme prérequis technique.

---

## 2. Positionnement produit

**Une phrase** : « Alfred is a Python package that turns raw AI-agent traces into a daily stand-up your team can actually trust — every line anchored to a trace event ID. »

**Deux phrases** : « You wouldn't hire a human employee without a manager, a mandate, and a paper trail. Alfred is that layer for your AI employees — declarative mandate in YAML, evidence-anchored digest in Slack, deviations flagged the moment they happen. »

**Positionnement vs voisins** (à mettre dans le README, section « Why not X ») :

| Outil | Ce qu'il fait | Ce qu'Alfred fait de différent |
|---|---|---|
| Langfuse / AgentOps / LangSmith | Observabilité *développeur* : traces, prompts, tokens, replay. | Compte-rendu *manager* : mandat vs réalité, écarts typés, digest quotidien lisible sans ouvrir de dashboard. |
| Guardrails / NeMo Guardrails | Filtres en ligne sur inputs/outputs LLM. | Contrôle *ex-post* sur toute la session d'agent, incluant outils appelés et coût. |
| Un dashboard Grafana / Datadog maison | Métriques agrégées, alerting. | Rapport narratif ancré, opinionated, sans avoir à designer les tableaux. |

---

## 3. Architecture v0.1

```
┌─────────────────────────────────────────────────────────────────┐
│  Sources de traces                                              │
│  ─ Fichiers OTLP JSON (fichier, watch dossier)                  │
│  ─ Endpoint OTLP HTTP (v0.2)                                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  alfred.trace  │  parse, normalise, valide
                    │  (ingest)      │
                    └───────┬────────┘
                            │  TraceEvent (dataclass immuable)
                    ┌───────▼────────┐
                    │  alfred.trace  │  SQLite (fichier local),
                    │  (store)       │  index par event_id, trace_id, ts
                    └───────┬────────┘
                            │
             ┌──────────────┼──────────────┐
             │              │              │
     ┌───────▼──────┐ ┌─────▼──────┐ ┌────▼──────────┐
     │ alfred.mandate│ │alfred.report│ │ alfred.deliver│
     │  YAML → règles│ │agrégats +   │ │  Slack (v0.1) │
     │  → Deviations │ │ancres event │ │  stdout (tjrs)│
     └───────────────┘ └─────┬───────┘ └───────────────┘
                             │
                     ┌───────▼────────┐
                     │  alfred.narrate │ optionnel — LLM
                     │  (verified NLG) │ vérifie que chaque
                     └─────────────────┘ phrase a ≥1 event_id
```

**Contrats internes** (invariants qui doivent tenir à travers toutes les briques) :

- `TraceEvent` est immuable et porte toujours un `event_id` stable et unique.
- `Digest` est une structure typée : chaque `Line` a un `sources: list[EventId]` non-vide. Un `Digest` sans sources sur une ligne est un bug à intercepter en test.
- Le module `narrate` ne peut émettre qu'un `NarratedDigest` où pour chaque phrase, les event IDs cités sont un sous-ensemble strict des `sources` de la ligne d'origine. Test obligatoire en B4.

---

## 4. Structure du repo

```
alfred/
├── pyproject.toml            # build, deps, ruff, mypy, pytest
├── README.md                 # court en dev, deviendra landing page en B6
├── CLAUDE.md                 # règles pour Claude Code (déjà écrit)
├── PLAN.md                   # ce document
├── LICENSE                   # Apache-2.0
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml            # à créer en B6 (tests + lint + mypy)
├── src/
│   └── alfred/
│       ├── __init__.py       # version, exports publics
│       ├── trace/
│       │   ├── __init__.py
│       │   ├── model.py      # TraceEvent, EventId, SpanKind
│       │   ├── ingest.py     # OTLP JSON → list[TraceEvent]
│       │   └── store.py      # SQLite persistence
│       ├── mandate/          # B2
│       │   ├── __init__.py
│       │   ├── model.py      # Mandate, Rule, Deviation
│       │   └── engine.py     # compare trace vs mandate
│       ├── report/           # B3
│       │   ├── __init__.py
│       │   ├── model.py      # Digest, Line, Source
│       │   └── build.py      # events + mandate → Digest
│       ├── narrate/          # B4
│       │   ├── __init__.py
│       │   └── llm.py        # Digest → NarratedDigest (LLM bridé)
│       ├── deliver/          # B5
│       │   ├── __init__.py
│       │   ├── slack.py
│       │   └── stdout.py
│       ├── demo/             # B6
│       │   ├── __init__.py
│       │   └── fake_agent.py # agent factice instrumenté
│       └── cli.py            # entrypoint `alfred` (init/watch/demo)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   └── otlp_sample.json
│   ├── test_trace_model.py
│   ├── test_trace_ingest.py
│   └── test_trace_store.py
└── docs/
    └── adr/                  # décisions architecturales datées
```

---

## 5. Roadmap — 6 briques v0.1

> **Statut v1.1 : les 6 briques sont livrées** (2026-07-18, `main` vert —
> preuve dans `docs/vcd/alfred-v0.1.md`). Restent les actions *publiques*
> de la DoD B6 (PyPI, tag, GIF, good first issues, org/domaine),
> absorbées par le sprint S0 de §11. Cette section est conservée comme
> contrat de référence.

Chaque brique est un **contrat** : objectif, tests falsifiables, definition-of-done, deliverable public. Le passage d'une brique à la suivante exige que la DoD précédente soit remplie et committée. Une semaine calendaire ≈ 5-7 heures de travail (contrainte CDI + 1h/jour ouvré + weekends partiels).

### Brique 1 — Trace store (semaine 1, ~28 août)

**Objectif** : ingérer un fichier OTLP JSON de traces d'agent, normaliser en `TraceEvent` immuables, persister en SQLite, retrouver par ID.

**Tests falsifiables** (déjà écrits dans le squelette) :
- `test_ingest_returns_all_spans` : fixture avec 3 spans → 3 `TraceEvent`.
- `test_ingest_preserves_span_id` : chaque event porte l'`event_id` du span d'origine.
- `test_ingest_extracts_gen_ai_attributes` : `gen_ai.usage.output_tokens` accessible sur l'event.
- `test_ingest_malformed_raises` : JSON invalide → `TraceIngestionError` typée.
- `test_store_roundtrip` : persiste 1 event → `get(event_id)` retourne l'event identique.
- `test_store_query_by_trace_id` : 3 events d'un même trace → `find(trace_id)` en retourne 3.

**Definition of done** : `pytest -q` vert, `mypy --strict src/alfred/trace` vert, commit `feat: brique 1 — trace store + otlp ingest`.

**Livrable public** : aucun (interne).

### Brique 2 — Mandate + moteur de déviations v0 (semaine 2)

**Objectif** : mandat YAML minimal (~5 lignes), moteur qui compare trace vs mandat et produit une `list[Deviation]` typée.

**Mandat cible v0.1** :
```yaml
# mandate.yaml
agent: refund-bot-v3
allowed_tools: [read_order, issue_refund, notify_customer]
daily_budget_eur: 5.00
forbidden_actions: [issue_refund_above_100_eur, send_marketing]
escalate_when: [tool_error_rate > 0.10, budget_used > 0.80]
```

**Types de déviations v0.1** : `tool_not_allowed`, `budget_exceeded`, `forbidden_action`, `escalation_missed`.

**Tests falsifiables** :
- Chaque type de déviation a un test qui construit une trace la déclenchant, et un test miroir qui vérifie qu'une trace conforme n'en génère aucune.
- `test_deviation_carries_event_ids` : chaque `Deviation` référence les `event_id` qui la prouvent.
- `test_mandate_yaml_roundtrip` : parse YAML → dump → parse retourne le même objet.

**Definition of done** : idem B1 + un fichier `examples/mandates/refund-bot.yaml` documenté.

**Livrable public** : aucun (interne).

### Brique 3 — Moteur de rapport (semaine 3)

**Objectif** : à partir des traces + mandat + déviations, produire un `Digest` typé. Sortie markdown et stdout.

**Format du digest v0.1** (fixe pour ne pas s'éparpiller) :
```
Alfred · refund-bot-v3 · 2026-08-30

Tasks completed:          47   [evt:a1c, a1d, a1e, …]
Cost (tokens → €):     3.42 €   [evt:c0f, …]
Escalations:               3   [evt:e01, e02, e03]
Deviations (mandate):      1   [evt:d0a] — tool_not_allowed: `read_pii`
```

**Tests falsifiables** :
- `test_digest_every_line_has_sources` : sur toute trace non-vide, chaque `Line` du `Digest` a `len(sources) >= 1`.
- `test_digest_sources_exist_in_store` : chaque `event_id` cité existe bien dans le trace store (pas de source fantôme).
- `test_digest_cost_matches_sum` : somme des coûts par event = coût total dans le digest.

**Definition of done** : idem + fixture "trace journée type" qui reproduit un digest de référence (test snapshot).

### Brique 4 — Verified NLG (semaine 4)

**Objectif** : optionnellement passer le `Digest` à un LLM pour reformulation en prose. Le test-clé garantit qu'**aucun fait n'apparaît sans event ID source**.

**Le test qui incarne la thèse du produit** :
```python
def test_narrated_digest_only_uses_source_events():
    digest = build_digest(traces, mandate)
    narrated = narrate(digest, llm_client=stub_llm)
    for sentence in narrated.sentences:
        cited = extract_event_ids(sentence.text)
        assert cited, f"Sentence with no event citation: {sentence.text}"
        assert cited.issubset(sentence.line.sources), (
            f"LLM cited events not in source: {cited - sentence.line.sources}"
        )
```

**Definition of done** : LLM configurable (OpenAI-compatible), stub LLM utilisé en test, doc `docs/verified_nlg.md` qui explique la garantie.

**Livrable public** : **un post technique** (« Comment on empêche notre LLM d'halluciner nos rapports ») — premier build-in-public post, pré-launch.

### Brique 5 — Livraison Slack + CLI (semaine 5)

**Objectif** : webhook Slack (Block Kit), commandes `alfred init` + `alfred watch`.

**Tests falsifiables** :
- `test_slack_payload_is_valid_block_kit` : le payload passe le validator Block Kit officiel (schéma inclus en fixture).
- `test_watch_ingests_new_files_only` : `watch` sur un dossier ne réingère pas un fichier déjà vu.
- `test_init_creates_config` : `alfred init` dans un dossier vide crée `mandate.yaml` + `.alfred/config.toml`.

**Definition of done** : idem + un test d'intégration end-to-end (fixture trace → digest → payload Slack, sans appel réseau réel).

**Livrable public** : aucun (interne — on garde la poudre pour B6).

### Brique 6 — `alfred demo` + polish launch (semaine 6, ~30 août)

**Objectif** : `alfred demo` lance un agent factice instrumenté, génère une vraie trace, produit un vrai digest. Zéro dépendance externe pour évaluer le produit.

**Critères de qualité du repo à la fin de B6** :
- README complet : GIF de démo en haut, quickstart 3 commandes, section « Why », comparatif, licence, statut open-core annoncé.
- CI GitHub Actions verte (pytest + ruff + mypy strict).
- `CHANGELOG.md`, `CONTRIBUTING.md`, templates d'issues, 3 `good first issue` étiquetées.
- Tag `v0.1.0` publié sur PyPI (`alfred-ai`).
- Le repo Alfred est lui-même vérifié par la méthodologie du harnais (VCD dans `docs/vcd/alfred-v0.1.md`).

**Definition of done du launch** : le repo passe le « test 5 minutes » — un inconnu clone, lit le README, lance `alfred demo`, voit un digest crédible dans son terminal en moins de 5 minutes.

**Livrable public** : c'est LE launch. Voir §6.

### Brique 7 — premier agent réel vérifié (ajoutée en v1.1, ADR 0010)

**Objectif** : un agent réel (boucle d'outils Claude sans framework,
`examples/agents/refund_bot/`) reçoit de vrais tickets, décide seul de ses
appels d'outils, émet une vraie trace OTLP — et `alfred watch` attrape (ou
pas : rien n'est scripté) sa déviation `forbidden_action` sous le mandat
`examples/mandates/refund-bot.yaml` existant. C'est la source du GIF de
launch et la réponse au « show me » d'une interview YC.

**Tests falsifiables** : `tests/test_example_refund_bot.py` (client LLM
scripté, zéro réseau) — trace ingestible, `tool.arguments.amount_eur` sur
`issue_refund`, usage réel propagé, run à 250 € → exactement une déviation
ancrée sur l'event ID du tool call, miroir conforme, erreur d'outil tracée.

**Definition of done** : tests verts en CI + **un run réel** (`run.py`,
clé API requise — action utilisateur) dont le digest attrape la déviation.
Le launch (§6.3) est re-daté seulement après ce run.

---

## 6. Plan marketing

### 6.1 Principes

Les stars viennent d'une **thèse racontée avec des preuves**. La thèse d'Alfred : *« on déploie des employés IA sans mandat, sans daily, sans dossier de preuve — voici la couche manquante »*. Chaque contenu la ré-encode. Aucun post ne parle du produit sans une preuve concrète (finding, code, GIF).

### 6.2 Pré-launch (compressé : 21 juillet → 3 août, ADR 0009)

Le build ayant fini à J+3, le pré-launch passe de 6 semaines à 2. Cibles
recalées : **15 noms** d'early users au 1er août (au lieu de 30 à J+45),
DM personnalisés vers ~8 d'entre eux dès que le GIF existe, objectif
inchangé de 5 installations le jour du launch + 2-3 témoignages écrits.
**2 posts build-in-public** au lieu de 6 : (1) le post B4 « comment on
empêche notre LLM d'halluciner nos rapports » — il est déjà documenté
dans `docs/verified_nlg.md`, c'est le plus fort ; (2) un post « pourquoi
vos agents IA ont besoin d'un mandat, pas d'un dashboard ».

**Cadence** : 1 post/semaine, EN + FR (X + LinkedIn), toujours sur un problème concret rencontré pendant la construction. Pas « j'ai codé la brique 3 » mais « voici pourquoi un agent qui résume sa propre activité hallucine, et comment on l'ancre sur la trace » (post issu de B4 par exemple).

**Constituer une liste d'early users pendant le build** (objectif : 30 noms à J+45) :
- Auteurs d'issues récentes sur `langchain-ai/langgraph`, `crewAIInc/crewAI`, `openai/openai-agents-python` qui mentionnent "monitoring", "tracing", "logging", "observability".
- Membres actifs du Discord de LangGraph et CrewAI (chercher les questions manager-side).
- r/AI_Agents contributeurs récents sur les threads "how do you monitor/audit agents".
- Ex-collègues systèmes critiques qui déploient de l'IA aujourd'hui (ton réseau — atout unique).

**Contact** : DM personnalisé à ~10 d'entre eux à J+35, montrer le GIF, demander « would you try this the day it ships? ». Objectif : 5 installations le jour du launch + 2-3 témoignages écrits (« I tried Alfred, here's what I got »).

**Assets à préparer à J+40** :
- GIF final de démo (< 15s, boucle propre).
- Post HN rédigé et relu.
- 3 tweets calibrés (thread + standalone + reply-bait).
- Post LinkedIn FR (angle manager/conformité).
- Post Reddit adapté par sub.

### 6.3 Launch (date **suspendue** — ADR 0010 ; re-datage après le run réel de la Brique 7. Séquence ci-dessous inchangée, translatable.)

**Séquence sur 5 jours ouvrés** (mardi → lundi suivant) :

| Jour | Canal | Angle | Objectif |
|---|---|---|---|
| Mardi 14h-16h Paris | **Show HN** | « Show HN: Alfred – daily stand-ups for your AI agents, computed from traces » | Front page, 100+ commentaires. Rester dispo 6h. |
| Mercredi | **Reddit** r/AI_Agents, r/LangChain, r/LocalLLaMA | Adapté par sub. LocalLLaMA = « surveillez vos agents sans envoyer vos traces à un SaaS ». | 500 upvotes cumulés. |
| Jeudi | **X thread** | GIF + le finding le plus frappant de B4 (verified NLG). | 200+ reposts sur le thread. |
| Vendredi | **LinkedIn FR** | Angle manager/conformité, ton réseau systèmes critiques. | 5 commentaires de décideurs. |
| Lundi J+7 | **Pitch 4 newsletters IA** (TLDR AI, The Rundown, Ben's Bites, La Revue IA) | Angle « accountability » = angle éditorial frais. | 1-2 pickups. |

**Signal de réussite du launch** : ≥ 500 stars à J+50, ≥ 20 installs pip, ≥ 5 issues créées par des inconnus.

**Si le launch rate** (< 100 stars à J+50) : ne pas paniquer, re-launch à J+120 avec la v0.2 sous un autre angle (« Alfred now speaks LangGraph natively »). Un HN raté se retente sous un autre angle à 2-3 mois.

### 6.4 Post-launch (J+50 → J+150)

> Déclinaison opérationnelle mois par mois (cibles intermédiaires, rythme
> hebdo, goulots du funnel) : `docs/GROWTH_PLAN_3M.md` (ADR 0011).

**Le moteur récurrent** :
- **Un finding public/mois** : issu de B4 puis du harnais agents. Chaque finding se conclut par « et voici comment ça apparaît dans le daily Alfred ».
- **Réactivité issues < 24h** les 3 premiers mois. C'est le signal de star le plus sous-estimé.
- **PRs d'exemples** dans les repos LangGraph, CrewAI, OpenAI Agents SDK (dossier `examples/`).
- **Soumission** aux awesome-lists : `awesome-llm-agents`, `awesome-ai-agents`, `awesome-opentelemetry`.
- **Leaderboard mensuel de fiabilité d'agents** (ancienne Brique 9 du harnais RAG, réactivée ici) — machine à contenu la plus starrable du plan. Premier édition à J+120.

**Cadence de release** :
- v0.2 (J+90) : connecteurs natifs LangGraph, CrewAI, OpenAI Agents SDK (priorisés par les *issues*, pas par intuition). Digest Teams. Coûts multi-providers.
- v0.3 (J+120) : « entretien de performance » — bench rejoué, dérive de comportement, coût/tâche vérifié.
- v0.4 (J+150) : chaîne de responsabilité — export dossier de preuve. C'est le pont explicite vers l'étage payant.

---

## 7. Cible YC 2027

### 7.1 Le dossier qui convertit

**v1.1 (ADR 0009)** : la candidature est déposée (2026-07-18). Ce tableau
n'est plus une cible à J+150 mais la trajectoire à démontrer *en continu*
— si une invitation à interview arrive, on présente la pente (courbe
d'installs et de stars depuis le launch du 4 août), pas le niveau absolu.
Les cibles chiffrées restent la référence pour un éventuel re-dépôt sur
un batch ultérieur :

| Élément | Cible à J+150 |
|---|---|
| Stars GitHub | 1 000+ |
| Installs pip/semaine | 500+ |
| Utilisateurs récurrents (daily actif ≥ 2 semaines) | 20+ |
| Équipes nommables en usage hebdomadaire | 3-5 |
| Lettres d'intention payantes | 1-2 |
| Demandes de payant/entreprise spontanées | 3+ |

**Le narratif** : « Le paquet pip a prouvé la demande (X installs, Y utilisateurs récurrents, Z équipes nommables). Le moteur de mandat vérifié — que nous gardons closed-source — est le fossé : la garantie formelle qu'aucune ligne du rapport n'est hallucinée, prouvée par notre méthodologie de vérification appliquée à notre propre code (le repo Alfred est vérifié avec le harnais qui l'a précédé). Nous levons pour recruter deux ingénieurs et vendre à trois secteurs régulés (assurance, finance, santé). »

### 7.2 Ce que la candidature exige que le plan produise

- **Une courbe d'installs** convaincante (données pip stats + PyPI).
- **Trois utilisateurs nommables** qui témoignent (les DM d'early users deviennent ces témoignages).
- **Une vidéo d'1 minute** du fondateur : toi, la thèse en 3 phrases, ton parcours vérification systèmes critiques comme légitimité unique.
- **Une réponse claire à « why now »** : agents IA en production explosent en 2026, aucun outil ne fait le compte-rendu manager, standards OTel GenAI en cours de stabilisation → fenêtre d'infrastructure ouverte.

### 7.3 Point de vigilance

YC exige le temps plein si accepté. À J+150 la décision « saut CDI → fondation » sera à trancher **avant** d'avoir toutes les données de traction souhaitées. Le plan §5 réserve donc J+120→J+150 pour la v0.4 (dossier de preuve) et la maximisation du signal payant.

---

## 8. Métriques et jalons de décision

**Revue mensuelle** (dernier vendredi de chaque mois) :

| Métrique | J+90 (bien) | J+150 (signal fort) |
|---|---|---|
| Stars GitHub | 300-500 | 1 000+ |
| Installs pip/semaine | 100 | 500+ |
| Utilisateurs récurrents (daily actif > 2 sem.) | 5 | 20+ |
| Demandes de connecteurs (issues) | 3 | 10+ |
| **Demandes de payant/entreprise spontanées** | 1 | 3+ |

**La ligne qui tranche** entre CDI premium / freelance-runway / fondation à J+150 = *demandes de payant spontanées*, pas stars. Si 0 à J+150 avec 1000 stars → le produit intéresse la communauté mais pas les acheteurs → repivoter le pitch payant, ne pas fonder.

---

## 9. Risques et garde-fous

| Risque | Garde-fou |
|---|---|
| Langfuse/AgentOps shippent des « manager reports » | README compare honnêtement dès J+45. Argument : « ils font l'observabilité *développeur*, nous le compte-rendu *manager* ». Le comparatif désamorce avant l'attaque. |
| Le daily auto-déclaré qui hallucine | Règle D5 encodée dans un test (B4). Article public à J+42 qui documente la garantie. C'est notre meilleur argument marketing. |
| AI Act reporté (accord politique du 07/05/2026 pour report au 02/12/2027) | Ne jamais dater d'argument sur août 2026. Cadre l'argument conformité sur « supervision humaine démontrable + journalisation » (art. 26 obligations déployeurs), intemporel. Surveiller la publication au JO. |
| Standards OTel GenAI/agents encore mouvants | Isoler `alfred.trace.ingest` derrière une couche d'adaptation. Les connecteurs natifs v0.2 réduisent la dépendance aux semconv. |
| Launch raté (arrive même avec un bon produit) | Un HN raté se retente à 3 mois sous un autre angle. Ne pas conclure sur un tir. |
| Épuisement à 1h/jour | Le scope v0.1 est volontairement minimal. **Tout ajout pré-launch = un « non » par défaut** (backlog explicite §10). |
| Faille dans la thèse « ancrage event ID » | Si un test B4 ne parvient pas à garantir la propriété : STOP, replanifier. La thèse est le produit. |

---

## 10. Backlog explicite (ce qu'on ne fait PAS en v0.1)

Décisions actives de *ne pas* faire, pour éviter la dérive :

- ❌ Dashboard web (v0.2 au plus tôt, sur demande utilisateurs).
- ❌ Multi-agents (v0.2+).
- ❌ Bench rejoué / dérive comportement (v0.3).
- ❌ Endpoint OTLP HTTP (v0.2, fichiers OTLP JSON suffisent pour v0.1).
- ❌ Connecteurs natifs LangGraph/CrewAI/OpenAI (v0.2, priorisés par issues).
- ❌ Digest Teams (v0.2), Discord (jamais sauf demande insistante).
- ❌ Base de données autre que SQLite (jamais en v0.x — zéro infra est un feature).
- ❌ Auth, RBAC, multi-tenancy (v0.4+, closed-source).
- ❌ Export dossier de preuve (v0.4 — c'est le pont vers le payant).
- ❌ Audit sécurité Trail of Bits (CodeQL/Semgrep) — prévu B5-B6, pas avant.

Backlog du harnais RAG (rappel D1) : B7-B9 sont documentées dans `BACKLOG_RAG.md` du repo harnais, pas ici. Le leaderboard (B9) reviendra en J+120 comme contenu marketing Alfred.

---

## 11. Sprint S0 « tout ce qui est public » (18–21 juillet, ADR 0009)

Dans cet ordre — le nom PyPI d'abord, chaque jour d'attente est un risque
de squat (`alfred-ai` vérifié libre le 2026-07-18) :

- [ ] Publier `alfred-ai 0.1.0rc1` sur PyPI (réserve le nom).
- [ ] Créer l'org GitHub `alfred-ai`, transférer le repo (AVANT le launch
      — les redirections préservent les liens, les stars s'accumulent à
      l'adresse définitive). Réserver le domaine (`getalfred.dev` ou `alfred.sh`).
- [ ] Enregistrer le GIF de démo (< 15 s, boucle propre) → haut du README.
- [ ] Ouvrir les 3 issues « good first issue ».
- [ ] Basculer le quickstart README sur `pip install alfred-ai`.
- [ ] Tag `v0.1.0` + release PyPI finale.

Puis, semaines du 21 et 28 juillet (pré-launch compressé, §6.2) :

- [ ] Publier le post B4 (« comment on empêche notre LLM d'halluciner nos
      rapports » — matière déjà dans `docs/verified_nlg.md`).
- [ ] Constituer la liste de 15 early users, DM ~8 avec le GIF.
- [ ] Rédiger le post Show HN + les assets §6.2 (thread X, LinkedIn FR, Reddit).
- [ ] Piste YC-readiness : vidéo fondateur 1 min, screencast démo 60 s,
      réponse « why now » écrite, suivi métriques hebdo (point zéro daté).
- [ ] **Launch mardi 4 août 14h-16h Paris** (séquence §6.3).

---

## 12. Sprint S1 « Bring Your Own Agent » (21 juillet →, ADR 0013)

**Objectif du sprint** : un dev qui clone le repo branche *son* agent sur
Alfred et obtient un digest ancré — sans copier-coller de code d'exemple,
sans attribut maison introuvable, sans format de fichier qui casse.

**Constat d'audit (2026-07-20)** qui dimensionne le sprint : (1) la seule
recette d'instrumentation est `examples/agents/refund_bot/tracer.py`,
example-only ; (2) le DSL `forbidden_actions` est câblé sur
`tool.arguments.amount_eur` et le budget du moteur ne lit que
`gen_ai.usage.cost_eur` — une trace OTel standard donne un budget consommé
de 0 € en silence ; (3) `ingest_otlp_file` ne lit pas le NDJSON du file
exporter de l'OTel Collector, et les erreurs d'outil ignorent le
`status.code` OTLP standard.

**Chemin critique launch** : B8 + B11. B9 et B10 peuvent suivre la semaine
du launch. Un commit par brique, mêmes exigences que §5 (`pytest -q`,
`ruff`, `mypy --strict src/` verts à chaque DoD).

### Brique 8 — `alfred.instrument` : SDK d'instrumentation public

**Objectif** : promouvoir la forme prouvée de `tracer.py` en module public
`alfred.instrument`, pour qu'une boucle d'agent quelconque s'instrumente en
~10 lignes. Émission OTLP JSON directe, exactement les clés que lisent
`ingest`/`engine`/`build` (neutralisation semconv de l'ADR 0010 conservée).
Zéro dépendance nouvelle.

**API cible** (forme, pas contrat figé — le test l'est) :

```python
from alfred.instrument import AgentTracer

tracer = AgentTracer(agent="support-bot", traces_dir="traces/")
with tracer.session():                                  # invoke_agent
    with tracer.llm_call(model="claude-opus-4-8") as llm:   # chat
        llm.record_usage(input_tokens=…, output_tokens=…)
    with tracer.tool_call("send_email", arguments={"to": …}) as tool:
        tool.record_result(status="ok")                 # execute_tool
tracer.flush()  # → traces/support-bot-<ts>.json
```

**Tests falsifiables** :
- `test_instrumented_loop_trace_ingests` : boucle jouet instrumentée →
  fichier → `ingest_otlp_file` → kinds corrects (`AGENT_TASK`, `LLM_CALL`,
  `TOOL_CALL`), event IDs uniques, timestamps cohérents.
- `test_tool_arguments_flattened` : `arguments={"amount_eur": 250.0}` →
  attribut `tool.arguments.amount_eur` sur le span.
- `test_tool_error_recorded` : exception dans le bloc `tool_call` →
  `tool.result.status != "ok"` (et l'exception se propage).
- `test_usage_propagated` : tokens et modèle présents sur le span LLM.
- `test_digest_from_instrumented_trace_anchored` : bout en bout jouet →
  chaque ligne du digest a `sources` non-vide.
- **Preuve de parité** : le refund-bot est refondu sur `alfred.instrument`
  et ses 6 tests existants (`tests/test_example_refund_bot.py`) restent
  verts **sans modification d'assertion** ; le `tracer.py` dupliqué est
  supprimé.

**Definition of done** : idem §5 + `docs/integrate.md` (quickstart
« instrumenter votre agent en 5 minutes »).

### Brique 9 — Mandat générique + coût depuis les tokens

**Objectif** : des règles de mandat sur n'importe quel outil et n'importe
quel argument, et un budget qui fonctionne sur une trace sans
`gen_ai.usage.cost_eur`.

**Forme YAML cible** (le DSL string actuel reste valide, rien ne casse) :

```yaml
forbidden_actions:
  - send_marketing                     # forme actuelle : nom d'outil
  - issue_refund_above_100_eur         # forme actuelle : DSL string
  - tool: execute_sql                  # nouvelle forme structurée
    when: args.rows_affected > 1000
```

**Tests falsifiables** :
- `test_structured_forbidden_rule_triggers` : règle structurée + trace la
  déclenchant → exactement une `Deviation` ancrée sur l'event ID du tool
  call ; `test_structured_forbidden_rule_conforming_trace` : miroir à zéro.
- `test_structured_rule_yaml_roundtrip` : parse → dump → parse identique.
- `test_legacy_dsl_unchanged` : `examples/mandates/refund-bot.yaml`
  inchangé, tests B2 existants verts sans modification.
- `test_budget_from_tokens_without_cost_attr` : trace avec tokens + modèle
  connu mais sans `cost_eur` → `budget_exceeded` et `budget_used`
  calculés depuis la table de prix (logique extraite de `report/build.py`
  vers `alfred.trace.cost`, consommée par les deux — même total au centime,
  vérifié par test).

**Definition of done** : idem + `examples/mandates/` gagne un exemple
commenté de règle structurée.

### Brique 10 — Ingestion du monde réel (OTel standard)

**Objectif** : le pont « agent OTel → Collector (file exporter) →
`alfred watch` » fonctionne, et les traces semconv standard sans clés
maison produisent erreurs d'outil et arguments exploitables. Tout le
mapping vit dans `alfred.trace.ingest` (garde-fou §9 : couche
d'adaptation) — le moteur de mandat ne change pas de vocabulaire.

**Tests falsifiables** :
- `test_ingest_ndjson_lines` : fichier 3 lignes JSON (forme file exporter
  Collector) → tous les spans ingérés ; fichier objet-unique → comportement
  actuel inchangé.
- `test_status_code_error_maps_to_tool_error` : span outil avec
  `status.code == STATUS_CODE_ERROR` et sans `tool.result.status` →
  `tool.result.status == "error"` après ingestion (jamais d'écrasement si
  la clé maison est présente).
- `test_tool_call_arguments_json_parsed` : `gen_ai.tool.call.arguments`
  (string JSON) → `tool.arguments.<clé>` pour chaque valeur scalaire.
- `test_malformed_ndjson_raises` : ligne invalide → `TraceIngestionError`
  avec numéro de ligne.

**Definition of done** : idem + section « OTel Collector bridge » dans
`docs/integrate.md` avec une config Collector minimale copiable.

### Brique 11 — Onboarding + « test 5 minutes BYOA »

**Objectif** : le « test 5 minutes » de la DoD B6, re-défini pour un agent
*externe* : un inconnu clone, lit le README, instrumente une boucle
minimale avec `alfred.instrument`, lance `alfred watch`, voit un digest
ancré — en moins de 5 minutes.

**Livrables** :
- `examples/agents/minimal/` : ~30 lignes, un agent jouet sans LLM (aucune
  clé API requise) instrumenté avec `alfred.instrument`, avec son mandat.
- Section README « Plug in your own agent » : les trois chemins (SDK
  `alfred.instrument` aujourd'hui, pont Collector, connecteurs natifs
  v0.2) — honnête sur les limites, comme le tableau « What's real ».
- `docs/integrate.md` consolidé (quickstart B8 + bridge B10).

**Tests falsifiables** : `test_minimal_example_end_to_end` : l'exemple
minimal, exécuté tel quel, produit une trace ingérée dont le digest a
toutes ses lignes ancrées (même esprit que le test refund-bot, zéro
réseau).

**Definition of done** : le test 5 minutes BYOA passe, chronométré par une
personne qui n'a pas écrit le code.

### Brique 12 — Connecteur natif LangGraph (ajoutée en v1.3, ADR 0014)

**Objectif** : un dev qui utilise LangGraph n'instrumente plus à la main.
Il attache un callback handler à l'invocation de son graphe et Alfred
enregistre ce que le graphe a réellement fait. Cible v0.2 avancée sur
demande produit — cloisonnée derrière l'extra optionnel `[langgraph]`, le
cœur garde `pyyaml` comme seule dépendance.

**Forme cible** (les ~3 lignes promises par `GROWTH_PLAN_3M.md`) :

```python
from alfred.instrument import AgentTracer
from alfred.integrations.langgraph import AlfredCallbackHandler

tracer = AgentTracer(agent="support-bot", traces_dir="traces")
graph.invoke(inputs, config={"callbacks": [AlfredCallbackHandler(tracer)]})
tracer.flush()
```

Le handler ne réémet aucune clé : il pilote les context managers prouvés
d'`AgentTracer` (`__enter__` sur `*_start`, `__exit__` sur `*_end`, indexés
par `run_id`). La garantie « chaque fait ancré sur un event ID réel » (D5)
est héritée, pas réimplémentée. `tracer.py` est inchangé.

**Tests falsifiables** (`tests/test_integration_langgraph.py`, vrai graphe
LangGraph + fake chat model, zéro réseau) :
- `test_graph_run_ingests` : run → 1 `AGENT_TASK`, ≥1 `LLM_CALL`, ≥1
  `TOOL_CALL`, event IDs uniques, enfants rattachés à la tâche.
- `test_tool_arguments_flattened` : `tool.arguments.amount_eur` sur le span
  outil ; `test_tool_error_recorded_as_status` : outil qui lève → statut
  `error`.
- `test_llm_usage_propagated` : tokens réels propagés depuis `usage_metadata`.
- `test_digest_from_graph_trace_anchored` : chaque ligne du digest a
  `sources` non-vide et ⊆ event IDs.
- `test_overlimit_yields_forbidden_action` : approbation à 250 € sous mandat
  cap 100 € → exactement une `Deviation FORBIDDEN_ACTION` ancrée sur l'event
  ID du tool call ; `test_conform_run_yields_no_deviations` : miroir à zéro.

**Definition of done** : idem §5 (`pytest -q`, `ruff`, `mypy --strict src/`
verts) + `examples/agents/langgraph_bot/` (agent jouet zéro clé) et section
« LangGraph connector » dans `docs/integrate.md`.

---

## 13. Features produit post-launch (backlog priorisé, 2026-07-22)

Cinq features retenues pour améliorer le produit *et* l'expérience client,
classées par levier. Chacune reste fidèle à la thèse (chaque affirmation ancrée
sur un event ID, rapport *manager* pas dashboard *dev*) et exige un ADR daté
avant code, mêmes DoD que §5 (`pytest -q`, `ruff`, `mypy --strict src/` verts).

| # | Feature | Pourquoi (expérience client) | Fit roadmap |
|---|---|---|---|
| F1 | **Alertes de déviation en temps réel** — push Slack immédiat dès qu'une passe trouve une déviation, en plus du digest quotidien. | Un manager ne découvre plus une erreur à 10 k€ le lendemain matin. Le plus gros trou d'expérience du produit. | Complémentaire, non listé au backlog §10. **ADR 0017.** |
| F2 | **Bootstrap du mandat depuis les traces + `alfred mandate lint`** — `mandate init --from-traces` propose outils autorisés et budget observés ; `lint` valide le YAML. | Tue la falaise d'onboarding (écrire le `mandate.yaml` juste). Raccourcit le time-to-value du « test 5 minutes BYOA » (Brique 11). | Prolonge la Brique 11. Non listé au backlog. |
| F3 | **Digest contextualisé par baseline glissante** — chaque chiffre gagne sa comparaison (« Coût 3.42 € — +180 % vs moy. 7 j ⚠️ »). | Transforme un nombre brut en jugement (« est-ce normal ? »). Cœur du créneau « rapport manager ». | Version *légère* de la dérive de comportement (v0.3), baseline seulement — pas le bench rejoué. |
| F4 | **Rapport HTML statique partageable** (`alfred report --html`) — fichier autonome, chaque ligne cliquable vers ses events source. | Le digest Slack est éphémère ; un manager veut *forwarder* la preuve navigable. | À cadrer en lecture seule, **délibérément plus pauvre** que l'export « dossier de preuve » payant (v0.4) pour ne pas le cannibaliser. Zéro infra (fichier généré, pas de dashboard web §10). |
| F5 | **Connecteurs natifs CrewAI + OpenAI Agents SDK** — la recette du connecteur LangGraph (Brique 12) pour les deux autres frameworks dominants. | Le *portail* avant toute expérience : un client ne peut pas brancher son stack sinon. | Roadmapé v0.2 (§6.4, « priorisés par les issues » — à confirmer par la demande réelle). |

**Mention honorable** : redaction PII/secrets avant stockage/envoi (feature de
confiance pour les secteurs régulés cibles YC — assurance/finance/santé). À
monter dans le top 5 si la priorité passe de l'adoption communautaire aux
secteurs régulés.

**Idée en réserve — sortie d'enforcement optionnelle** : sur détection d'une
déviation, appeler un hook externe (kill switch, révocation de credentials,
blocage d'outil) en plus du reporting. Ferait passer Alfred de « je constate /
j'alerte » à « j'alerte *et* je peux déclencher une coupure », sans trahir la
règle produit : le hook reste **strictement séparé** du moteur de reporting, et
chaque déclenchement reste ancré à l'`event_id` de la déviation qui l'a causé.
Motivé par les incidents type « agent qui enchaîne N milliers d'actions
autonomes sur un week-end sans humain dans la boucle » : l'alerte near-real-time
(F1) réduit la fenêtre, l'enforcement la fermerait. Limite assumée à documenter
dans l'ADR : reste aveugle à ce qui sort du périmètre tracé (un agent qui
« s'échappe » de son instrumentation). À cadrer en ADR daté avant tout code.

**Séquencement retenu** : F1 puis F2 d'abord — plus fort levier d'expérience
*sans* toucher au périmètre payant, et les plus rapides à shipper post-launch.
**F1 est en cours** (ADR 0017).

---

*Modifications : tout écart à ce document doit être précédé d'une entrée `docs/adr/NNNN-titre.md` datée et signée. Aucun refactor cosmétique.*

# Alfred — Plan opérationnel

> Source de vérité unique. Toute décision qui contredit ce document doit
> soit modifier ce document, soit être documentée dans un ADR daté sous
> `docs/adr/`. Pas de plan parallèle en tête ou en Notion.

**Version** : 1.0 · **Date** : 2026-07-15 · **Cible produit** : v0.1 publique à J+45 (30 août 2026).
**Cible fondateur** : dossier YC 2027 lisible à J+150 (12 décembre 2026).

---

## 1. Décisions actées (verrouillé)

| # | Décision | Impact |
|---|---|---|
| D1 | **Séquencement hybride RAG→Alfred** : finir la Brique 6 du harnais RAG (en cours). Geler B7-B9 en backlog. Attaquer Alfred immédiatement après. | Launch Alfred déplacé de J+150 à J+45 (~30 août 2026). |
| D2 | **YC : cible unique = candidature sérieuse 2027** (Winter ou Summer 2027 selon les métriques à J+150). Pas de candidature-exercice Fall 2026. | Pas de sprint pitch parallèle. Le plan produit devient le pitch. |
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

---

## 6. Plan marketing

### 6.1 Principes

Les stars viennent d'une **thèse racontée avec des preuves**. La thèse d'Alfred : *« on déploie des employés IA sans mandat, sans daily, sans dossier de preuve — voici la couche manquante »*. Chaque contenu la ré-encode. Aucun post ne parle du produit sans une preuve concrète (finding, code, GIF).

### 6.2 Pré-launch (S1→S6, pendant le build)

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

### 6.3 Launch (J+45 à J+50, semaine du 30 août 2026)

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

À constituer à J+150 (décembre 2026) pour candidature Winter 2027 (deadline typique ~octobre 2026 — **à vérifier une fois la date officielle publiée**) ou Summer 2027 :

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

## 11. Prochaines actions immédiates (48h)

- [ ] Réserver `alfred-ai` sur PyPI, l'org GitHub `alfred-ai`, un domaine (`getalfred.dev` ou `alfred.sh`).
- [ ] Finir la Brique 6 du harnais RAG sans dévier vers B7 (D1).
- [ ] Tag `v1.0` du harnais RAG, publier `BACKLOG_RAG.md` avec B7-B9 documentées.
- [ ] Première session Claude Code sur Alfred : implémenter les stubs de la Brique 1 pour rendre `pytest -q` vert (le squelette et les tests sont déjà en place — voir `src/alfred/trace/` et `tests/`).
- [ ] Commit `feat: brique 1 — trace store + otlp ingest`.

---

*Modifications : tout écart à ce document doit être précédé d'une entrée `docs/adr/NNNN-titre.md` datée et signée. Aucun refactor cosmétique.*

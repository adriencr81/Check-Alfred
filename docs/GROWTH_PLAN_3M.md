# Alfred — Plan de croissance 3 mois (19 juillet → 19 octobre 2026)

> Document opérationnel qui détaille PLAN.md §6 (marketing) et §6.4/§8
> (post-launch, métriques) sur un horizon de 3 mois. Il ne contredit
> aucune décision actée — voir `docs/adr/0011-growth-plan-3m.md`.
> **Objectif unique : maximiser le nombre d'utilisateurs.**

**Version** : 1.0 · **Date** : 2026-07-19 · **Horizon** : M1 (19/07→18/08),
M2 (19/08→18/09), M3 (19/09→19/10).

---

## 0. Métrique nord et définitions

**Métrique nord** : **utilisateurs récurrents** = installations qui génèrent
un digest ≥ 2 semaines d'affilée (auto-déclaré via issues/DM — pas de
télémétrie dans le paquet, c'est un argument produit).

**Métriques proxy** (mesurables sans télémétrie, suivi hebdo dès la
publication PyPI, point zéro daté — ADR 0009 décision 4) :

| Proxy | Source | Fréquence |
|---|---|---|
| Installs pip/semaine | pypistats.org | hebdo (vendredi) |
| Stars GitHub | API GitHub | hebdo |
| Issues/PRs d'inconnus | GitHub | hebdo |
| Clones uniques | GitHub traffic | hebdo |
| Mentions (HN, Reddit, X) | recherche manuelle | hebdo |

**La ligne qui compte** (PLAN.md §8, inchangée) : les demandes de payant
spontanées tranchent la suite — mais sur 3 mois, tout est optimisé pour le
haut du funnel : *découverte → installation → premier digest → habitude*.

**Le funnel et son goulot par mois** :

| Mois | Goulot attaqué | Levier principal |
|---|---|---|
| M1 | **Découverte** | Launch multi-canal (§6.3) + assets publics |
| M2 | **Installation → 1er digest** | Connecteurs natifs v0.2 (zéro friction) |
| M3 | **Habitude + boucle virale** | Leaderboard mensuel + re-launch angle v0.2 |

---

## 1. Mois 1 — Launch & activation (19 juillet → 18 août)

### 1.1 Technique (au service de l'acquisition)

Priorité 1 — **Sprint S0 « tout ce qui est public »** (PLAN.md §11, dans
cet ordre, le nom PyPI d'abord) :

- [ ] `alfred-ai 0.1.0rc1` sur PyPI (réserve le nom).
- [ ] Org GitHub `alfred-ai` + transfert du repo + domaine.
- [ ] GIF de démo < 15 s en haut du README.
- [ ] 3 « good first issue » ouvertes.
- [ ] Quickstart README basculé sur `pip install alfred-ai`.
- [ ] Tag `v0.1.0` + release PyPI finale.

Priorité 2 — **réduire le time-to-first-digest sous 5 minutes pour un
inconnu pressé** (chaque friction du quickstart coûte des utilisateurs le
jour du launch) :

- [ ] `pipx run alfred-ai demo` / `uvx alfred-ai demo` fonctionnels et
      documentés — l'essai sans même créer un venv.
- [ ] Messages d'erreur du CLI relus : chaque erreur probable du premier
      quart d'heure (OTLP invalide, mandat YAML mal formé, webhook Slack
      absent) doit dire *quoi faire*, pas seulement *quoi s'est passé*.
      Test falsifiable par cas d'erreur avant toute modification.
- [ ] Page GitHub Pages minimale (mkdocs, thème par défaut) : quickstart,
      « Why », comparatif — la landing citée dans tous les posts.

Priorité 3 — **fiabilité visible** : badge CI déjà en place ; ajouter le
badge PyPI + Python versions au README après publication.

**Gel des features** : aucune feature produit en M1 (PLAN.md §9, « tout
ajout pré-launch = non par défaut »). Le travail technique de M1 est
exclusivement du polish d'entonnoir.

### 1.2 Marketing

Semaine du 21/07 (pré-launch, §6.2 compressé) :
- [ ] Post build-in-public n°1 : « Comment on empêche notre LLM
      d'halluciner nos rapports » (matière : `docs/verified_nlg.md`). EN
      (X + HN en « Show » léger) + FR (LinkedIn).
- [ ] Liste de 15 early users constituée (issues LangGraph/CrewAI/OpenAI
      Agents mentionnant monitoring/observability ; Discords ; r/AI_Agents ;
      réseau systèmes critiques).

Semaine du 28/07 :
- [ ] Post n°2 : « Vos agents IA ont besoin d'un mandat, pas d'un
      dashboard ».
- [ ] DM personnalisés à ~8 early users avec le GIF (« would you try this
      the day it ships? »). Objectif : 5 installs jour J + 2-3 témoignages.
- [ ] Assets launch finalisés : post Show HN relu, thread X, LinkedIn FR,
      posts Reddit adaptés par sub.

Semaine du 04/08 — **LAUNCH** (séquence §6.3 inchangée) :
mardi Show HN 14h-16h Paris → mercredi Reddit (r/AI_Agents, r/LangChain,
r/LocalLLaMA) → jeudi thread X → vendredi LinkedIn FR → lundi 11/08 pitch
4 newsletters (TLDR AI, The Rundown, Ben's Bites, La Revue IA).

Semaines du 11/08 et 18/08 (post-launch immédiat) :
- [ ] **Réactivité issues < 24 h** — le signal de traction le plus
      sous-estimé, et le moins cher.
- [ ] Répondre à *tous* les commentaires HN/Reddit pendant 7 jours.
- [ ] Soumission aux awesome-lists : `awesome-llm-agents`,
      `awesome-ai-agents`, `awesome-opentelemetry`.
- [ ] Bilan launch au 10-14/08 contre le signal §6.3 (≥ 500 stars,
      ≥ 20 installs, ≥ 5 issues d'inconnus). Si < 100 stars : appliquer le
      garde-fou §9 (re-launch M3 sous l'angle v0.2), ne rien conclure.

### 1.3 Cibles fin M1

| Métrique | Cible |
|---|---|
| Stars | 500 (signal §6.3) — plancher acceptable 150 |
| Installs pip/semaine | 20-50 |
| Issues/PRs d'inconnus | ≥ 5 |
| Témoignages écrits early users | 2-3 |

---

## 2. Mois 2 — Rétention & friction zéro : v0.2 (19 août → 18 septembre)

Thèse du mois : **le launch a créé la découverte ; la v0.2 convertit la
découverte en usage**. Le plus gros abandon attendu : « j'utilise
LangGraph/CrewAI, je ne sais pas produire vos fichiers OTLP ». Les
connecteurs natifs suppriment cette marche.

### 2.1 Technique — v0.2 (~J+90, PLAN.md §6.4)

Priorisation **par les issues réelles du launch**, pas par intuition.
Ordre par défaut si les issues ne tranchent pas :

- [ ] **Connecteur LangGraph** (communauté la plus large) : `pip install
      alfred-ai[langgraph]`, 3 lignes pour instrumenter, exemple complet
      dans `examples/`.
- [ ] **Connecteur OpenAI Agents SDK**, puis **CrewAI** — même contrat :
      chaque connecteur a un test d'intégration falsifiable (trace émise →
      digest ancré) et un exemple exécutable.
- [ ] **Endpoint OTLP HTTP** (sort du backlog §10, prévu v0.2) : les
      agents streament leurs traces sans passer par des fichiers.
- [ ] Digest **Teams** + coûts multi-providers (si demandés par issues —
      sinon glissent en v0.3).
- [ ] Chaque connecteur isolé derrière la couche d'adaptation
      `alfred.trace.ingest` (garde-fou §9 sur les semconv mouvants).

**Discipline inchangée** : test falsifiable d'abord, mypy --strict, un
commit par brique, ADR si écart au plan.

### 2.2 Marketing

- [ ] **Un finding public** (le moteur récurrent §6.4) : cas réel ou
      reproductible où Alfred attrape une déviation que le résumé
      auto-déclaré de l'agent masquait. Conclusion rituelle : « voici
      comment ça apparaît dans le daily Alfred ». Ce post est LE modèle
      qui se répète chaque mois.
- [ ] **PRs d'exemples dans les repos des frameworks** (LangGraph, CrewAI,
      OpenAI Agents SDK, dossier `examples/`) — chaque PR mergée est un
      backlink permanent devant la communauté cible.
- [ ] Cadence maintenue : 1 post/semaine EN+FR, toujours un problème
      concret + une preuve (règle §6.1).
- [ ] **Activer les early users comme relais** : demander aux 2-3
      témoins de M1 un post court « I tried Alfred, here's what I got »
      (co-rédaction proposée).
- [ ] Réactivité issues < 24 h, toujours.
- [ ] Release **v0.2 annoncée comme un mini-launch** (changelog narratif,
      thread X, post Reddit sur le sub du framework connecté :
      « Alfred now speaks LangGraph natively »).

### 2.3 Cibles fin M2 (≈ revue « J+90 » de PLAN.md §8, recalée ADR 0009)

| Métrique | Cible (colonne « J+90 bien » §8) |
|---|---|
| Stars | 300-500 cumulées (ou +50 % vs fin M1 si launch modeste) |
| Installs pip/semaine | 100 |
| Utilisateurs récurrents | 5 |
| Demandes de connecteurs (issues) | 3+ (elles priorisent la suite) |
| Demandes payant spontanées | 1 |

---

## 3. Mois 3 — Boucles de croissance : v0.3 + leaderboard (19 septembre → 19 octobre)

Thèse du mois : passer du marketing *linéaire* (un post = un pic) aux
**machines à contenu récurrentes** qui rapportent des utilisateurs chaque
mois sans effort marginal.

### 3.1 Technique — v0.3 (~J+120, PLAN.md §6.4)

- [ ] **« Entretien de performance »** : bench rejoué, dérive de
      comportement, coût/tâche vérifié — chaque affirmation ancrée sur des
      event IDs (règle D5, non négociable).
- [ ] **Infra du leaderboard mensuel de fiabilité d'agents** (Brique 9
      réactivée, §6.4) : harnais qui rejoue N agents/frameworks publics
      sous un même mandat et publie le classement des déviations. Sortie
      = page statique + données brutes committées (reproductible par
      quiconque — c'est la crédibilité).
- [ ] Dette d'entonnoir : traiter les 5 frictions d'installation les plus
      citées dans les issues depuis le launch.

### 3.2 Marketing

- [ ] **Leaderboard édition n°1** (~J+120, mi-octobre) — l'actif le plus
      starrable du plan : classement mensuel public « quel framework
      d'agents dévie le moins de son mandat ». Chaque édition est un
      Show HN / post Reddit naturel, et chaque framework classé a une
      communauté qui viendra vérifier.
- [ ] **Re-launch si nécessaire** (garde-fou §9) : si le launch M1 a fait
      < 100 stars, re-tir HN sous l'angle « Alfred now speaks LangGraph
      natively » — un HN raté se retente à 2-3 mois sous un autre angle.
- [ ] Finding public du mois (cadence rituelle).
- [ ] **2-3 études de cas nommées** tirées des utilisateurs récurrents
      (matière YC §7.2 : « trois utilisateurs nommables »).
- [ ] Talk/meetup : 1 candidature à un meetup IA (Paris AI/GenAI, ou
      virtual) avec la démo refund-bot en live — le « show me » de la
      Brique 7 est déjà prêt.
- [ ] Pitch rond 2 des newsletters avec le leaderboard comme angle frais.

### 3.3 Cibles fin M3

| Métrique | Cible |
|---|---|
| Stars | 700-1 000 (trajectoire « J+150 » §8) |
| Installs pip/semaine | 250-500 |
| Utilisateurs récurrents | 10-20 |
| Équipes nommables | 2-3 |
| Demandes payant spontanées | 2+ |

---

## 4. Rythme hebdomadaire (les 3 mois, invariant)

| Jour | Rituel |
|---|---|
| Lundi | Tri des issues (< 24 h de latence maintenue toute la semaine) |
| Mercredi | Rédaction/publication du post de la semaine |
| Vendredi | Relevé métriques (pypistats, stars, issues, clones) → tableau de suivi hebdo ; revue mensuelle le dernier vendredi (§8) |

## 5. Garde-fous (rappels, tous déjà actés)

- **Aucune affirmation marketing sans preuve** (§6.1) : chaque post
  contient un finding, du code ou un GIF.
- **Règle D5** : si une feature de v0.2/v0.3 ne peut pas ancrer ses
  affirmations sur des event IDs → STOP, replanifier.
- **Priorisation par issues, pas par intuition** (§6.4) : les connecteurs
  et le digest Teams n'avancent que tirés par la demande.
- **Pas de télémétrie dans le paquet** : la mesure d'usage reste
  proxy-based ; « vos traces restent chez vous » est un argument
  d'acquisition (angle r/LocalLLaMA).
- **Un tir raté ne conclut rien** (§9) : le re-launch M3 est déjà budgété.
- **Épuisement** (contrainte ~1 h/jour) : chaque mois a UNE priorité
  technique et UNE machine marketing ; tout le reste est backlog.

## 6. Ce qu'on ne fait PAS sur ces 3 mois

Rappel du backlog négatif §10, appliqué à l'horizon : pas de dashboard
web (sauf demande massive par issues), pas de multi-tenancy/auth, pas
d'autre base que SQLite, pas de Discord, pas d'audit sécurité externe
avant v0.4. L'export dossier de preuve (v0.4, pont vers le payant) démarre
*après* cet horizon, vers J+150.

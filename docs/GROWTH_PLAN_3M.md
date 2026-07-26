# Alfred — Plan de croissance 3 mois (19 juillet → 19 octobre 2026)

> Document opérationnel qui détaille PLAN.md §6 (marketing) et §6.4/§8
> (post-launch, métriques) sur un horizon de 3 mois. Il ne contredit
> aucune décision actée — voir `docs/adr/0011-growth-plan-3m.md`.
> **Objectif unique : maximiser le nombre d'utilisateurs.**

**Version** : 1.1 · **Date** : 2026-07-25 · **Horizon** : M1 (19/07→18/08),
M2 (19/08→18/09), M3 (19/09→19/10).

> **Révision 1.1 (2026-07-25, ADR 0027)** — trois recalages : le vivier
> « réseau systèmes critiques » n'existe pas, donc le sourcing devient
> intégralement froid (30 noms) ; le créneau du vendredi passe aux PRs
> d'exemples et aux awesome-lists ; et surtout **les connecteurs natifs qui
> constituaient tout le levier de M2 sont livrés** (Briques 12 et 13, ADR 0014
> et 0021, postérieures à la v1.0 de ce document). Le M2 est recalé en
> conséquence — voir §2.

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
| **Digests partagés** | issues `show-your-digest` | hebdo |

Le dernier est le seul proxy qui prouve une **exécution**, pas une intention :
les autres comptent des gens qui ont vu le projet, celui-là compte des gens qui
l'ont fait tourner sur leur propre agent (ADR 0027 décision 9).

**La ligne qui compte** (PLAN.md §8, inchangée) : les demandes de payant
spontanées tranchent la suite — mais sur 3 mois, tout est optimisé pour le
haut du funnel : *découverte → installation → premier digest → habitude*.

**Le funnel et son goulot par mois** :

| Mois | Goulot attaqué | Levier principal |
|---|---|---|
| M1 | **Découverte** | Launch multi-canal (§6.3) + assets publics — connecteurs natifs déjà livrés, donc dans l'angle du launch et non plus du M2 |
| M2 | **Installation → 1er digest** | Ce que les issues du launch désignent : CrewAI, endpoint OTLP HTTP, frictions d'install |
| M3 | **Habitude + boucle virale** | Leaderboard mensuel + re-launch si nécessaire |

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

- [x] `pipx run alfred-ai demo` / `uvx alfred-ai demo` fonctionnels et
      documentés (2026-07-26) — l'essai sans même créer un venv. Les deux
      lanceurs cherchent un exécutable portant le nom de la *distribution*,
      donc un alias `alfred-ai` a été ajouté à côté de `alfred` : sans lui la
      commande annoncée échoue sur un paquet parfaitement installé. Chemin
      `uvx` vérifié depuis un wheel local ; `pipx` non vérifiable dans
      l'environnement de vérification (son binaire refuse de démarrer contre
      l'`uv` présent). Alias verrouillé par `tests/test_version.py`.
- [x] Messages d'erreur du CLI relus (2026-07-26) : les trois erreurs du
      premier quart d'heure nomment le geste qui les répare — projet absent
      → `alfred init <dir>`, mandat YAML cassé → le chemin du fichier puis
      `alfred mandate lint`, et une passe qui met tout en quarantaine ne
      prétend plus « no new trace files ». OTLP invalide et webhook Slack
      absent étaient déjà actionnables. Un test falsifiable par cas.
- [x] Page GitHub Pages minimale (mkdocs, thème par défaut) : quickstart,
      « Why », comparatif — la landing citée dans tous les posts (2026-07-26).
      `docs_dir` est `docs/site`, **pas** `docs/` : ce dernier contient ce
      document (cibles YC, seuils de revenu, critère CDI/fondation), la VCD et
      les ADR — les publier comme documentation officielle sur un site indexé
      est une exposition différente de leur présence dans un dossier du repo.
      Publication opt-in, un fichier à la fois. Reste une action mainteneur :
      Settings → Pages → Source = GitHub Actions.
- [x] `alfred schedule --github-actions` : un digest quotidien qui tourne
      sans machine allumée. Attaque le goulot de M3 (l'habitude) dès M1,
      parce que sans lui la métrique nord est inatteignable pour quiconque
      n'a pas de serveur (ADR 0027).
- [x] `alfred demo` invite à partager le digest obtenu (+ template d'issue) :
      le seul signal d'activation possible sans télémétrie.

Priorité 3 — **fiabilité visible** : badges CI, PyPI, versions Python et
licence en place au README (2026-07-26). Les deux badges PyPI restent vides
tant que le paquet n'est pas publié — c'est leur état normal avant le tag.

**Gel des features** : aucune feature produit en M1 (PLAN.md §9, « tout
ajout pré-launch = non par défaut »). Le travail technique de M1 est
exclusivement du polish d'entonnoir. **Exception tracée le 2026-07-25**
(ADR 0027 décision 1) : les deux items cochés ci-dessus sont classés polish
d'entonnoir — ils ne changent ni ce qu'Alfred calcule ni la règle D5, l'un
change la façon dont `watch` est déclenché, l'autre ajoute une ligne de
texte. C'est un jugement, contestable en revue mensuelle.

### 1.2 Marketing

Semaine du 21/07 (pré-launch, §6.2 compressé) :
- [ ] Post build-in-public n°1 : « Comment on empêche notre LLM
      d'halluciner nos rapports » (matière : `docs/verified_nlg.md`). EN
      (X + HN en « Show » léger) + FR (LinkedIn).
- [ ] Liste de 30 early users constituée — viviers §6.2 (issues des
      frameworks, issues des outils adjacents, HN via Algolia, auteurs de
      billets, Discords, r/AI_Agents, r/LocalLLaMA). Sourcing intégralement
      froid : le vivier « réseau » du plan initial n'existe pas.
- [ ] **Échauffement des comptes Reddit** : commentaires sincères dans
      r/AI_Agents et r/LocalLLaMA. Même activité que le sourcing ci-dessus,
      et prérequis pour que les posts du launch ne soient pas filtrés.

Semaine du 28/07 :
- [ ] Post n°2 : « Vos agents IA ont besoin d'un mandat, pas d'un
      dashboard ».
- [ ] DM personnalisés à ~15 early users avec le GIF (« would you try this
      the day it ships? »). Objectif : 5 installs jour J + 2-3 témoignages.
- [ ] Assets launch finalisés : post Show HN relu (angle connecteurs
      natifs), thread X, posts Reddit adaptés par sub, PRs d'exemples
      préparées.

Semaine du 04/08 — **LAUNCH** (séquence §6.3, révisée ADR 0027) :
mardi Show HN 14h-16h Paris → mercredi Reddit (r/AI_Agents, r/LocalLLaMA,
posts texte) → jeudi thread X → vendredi PRs d'exemples + awesome-lists →
lundi 11/08 pitch 4 newsletters (TLDR AI, The Rundown, Ben's Bites,
La Revue IA).

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
| **Digests partagés publiquement** | ≥ 3 |

Sur la lecture du résultat : un Show HN suit une distribution très asymétrique.
L'issue la plus probable est nettement sous les 500 stars, qui correspondent en
réalité à un top 10 front page. Le garde-fou §9 est écrit pour ça — **un tir
raté ne conclut rien**, le re-launch M3 est déjà budgété. Les digests partagés,
eux, se lisent au premier jour : trois personnes qui montrent une sortie réelle
valent plus, pour la suite du plan comme pour §7.2, que trois cents stars.

---

## 2. Mois 2 — Rétention & friction zéro : v0.2 (19 août → 18 septembre)

Thèse du mois : **le launch a créé la découverte ; le M2 la convertit en
usage**. La v1.0 de ce document pariait tout le mois sur les connecteurs
natifs, censés supprimer la marche « je ne sais pas produire vos fichiers
OTLP ». **Cette marche est déjà supprimée** : LangGraph (Brique 12, ADR 0014)
et OpenAI Agents SDK (Brique 13, ADR 0021) sont livrés, testés en CI et
documentés dans `docs/integrate.md`. Ils appartiennent donc à l'angle du
launch, pas au M2.

Ce que ça change : le M2 n'a plus de levier décidé d'avance. Il est
**intégralement piloté par les issues du launch** — ce qui était déjà la
règle (§6.4, « priorisation par les issues, pas par intuition »), mais qui
devient la seule règle. Ne rien pré-décider ici est le comportement correct,
pas un trou dans le plan.

### 2.1 Technique — v0.2 (~J+90, PLAN.md §6.4)

Livré avant le launch, à ne pas replanifier :

- [x] **Connecteur LangGraph** — `pip install alfred-ai[langgraph]`, un
      callback handler, exemple exécutable dans `examples/agents/langgraph_bot/`.
- [x] **Connecteur OpenAI Agents SDK** — `pip install alfred-ai[openai-agents]`,
      un tracing processor, exemple dans `examples/agents/openai_agents_bot/`.

Reste à faire, dans l'ordre que les issues désignent :

- [ ] **Connecteur CrewAI** — même contrat que les deux précédents : test
      d'intégration falsifiable (vrai run du framework, zéro réseau → digest
      ancré) et exemple exécutable.
- [ ] **Endpoint OTLP HTTP** (sort du backlog §10, prévu v0.2) : les
      agents streament leurs traces sans passer par des fichiers.
- [ ] Digest **Teams** + coûts multi-providers (si demandés par issues —
      sinon glissent en v0.3).
- [ ] **Dette d'entonnoir du launch** : les frictions d'installation les plus
      citées dans les issues. Remontée de M3, parce qu'une friction signalée
      par un inconnu pendant le launch coûte des utilisateurs tant qu'elle
      dure.
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
- [ ] **PRs d'exemples dans les repos des frameworks** — poursuivies et
      relancées ; les premières partent dès le vendredi du launch (§6.3).
      Chaque PR mergée est un backlink permanent devant la communauté cible.
- [ ] Cadence maintenue : 1 post/semaine EN+FR, toujours un problème
      concret + une preuve (règle §6.1).
- [ ] **Activer les early users comme relais** : demander aux 2-3
      témoins de M1 un post court « I tried Alfred, here's what I got »
      (co-rédaction proposée).
- [ ] Réactivité issues < 24 h, toujours.
- [ ] Release **v0.2 annoncée comme un mini-launch** (changelog narratif,
      thread X, post Reddit sur le sub du framework nouvellement connecté).
      L'angle « Alfred now speaks X natively » est désormais celui du launch
      lui-même : le mini-launch M2 porte donc ce que le M1 n'avait pas —
      CrewAI, ou l'endpoint OTLP HTTP, selon ce que les issues ont désigné.

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
- [ ] Dette d'entonnoir : le reliquat de ce que le M2 n'a pas absorbé
      (§2.1), pas un lot neuf.

### 3.2 Marketing

- [ ] **Leaderboard édition n°1** (~J+120, mi-octobre) — l'actif le plus
      starrable du plan : classement mensuel public « quel framework
      d'agents dévie le moins de son mandat ». Chaque édition est un
      Show HN / post Reddit naturel, et chaque framework classé a une
      communauté qui viendra vérifier.
- [ ] **Re-launch si nécessaire** (garde-fou §9) : si le launch M1 a fait
      < 100 stars, re-tir HN — un HN raté se retente à 2-3 mois sous un autre
      angle. L'angle connecteurs étant consommé au M1, c'est **le leaderboard**
      qui porte le re-tir : un classement public est un objet de discussion
      neuf, pas une redite du produit.
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

# Alfred — Plan « vitrine GitHub »

> Analyse des dépôts qui ont le mieux réussi sur les 6 derniers mois
> (janvier → juillet 2026) et plan d'application à ce dépôt.
> Complète `docs/GROWTH_PLAN_3M.md` (quels canaux, quel calendrier) en
> répondant à une autre question : **ce que voit quelqu'un qui arrive.**

**Version** : 1.0 · **Date** : 2026-07-26 · **Horizon** : avant le launch v0.1
(early août 2026), puis entretien continu.

---

## 0. La thèse en une phrase

Alfred est le seul projet de son marché dont la **règle produit est une
falsifiabilité** — et c'est exactement l'argument que tous les gagnants des 6
derniers mois passent leur README à essayer de fabriquer. Le dépôt possède déjà
l'actif marketing le plus rare de la catégorie ; **il ne l'expose pas.** Le
README *énonce* la règle en prose, il ne la **montre** jamais.

Tout ce plan découle de là : arrêter de décrire Alfred, le faire se prouver
au-dessus de la ligne de flottaison.

---

## 1. Méthode et corpus

Recherche GitHub sur `created:>2026-01-01`, tri par étoiles, deux passes
(`topic:ai-agents stars:>2000` → 103 dépôts ; `language:Python stars:>1500` →
389 dépôts). Lecture structurelle des READMEs des trois plus proches d'Alfred.

**Avertissement de sélection, qui vaut décision.** Le haut du classement n'est
pas imitable et ne doit pas l'être :

| Dépôt | Étoiles (6 mois) | Pourquoi non-imitable |
|---|---|---|
| `affaan-m/ECC` | 233 k | Harness pour agents de code — surfe la vague Claude Code, distribution ≫ produit |
| `Graphify-Labs/graphify` | 96 k | 25 langues de README, backing YC, équipe |
| `sickn33/agentic-awesome-skills` | 44 k | Catalogue de 1 987 skills — logique d'annuaire, pas de produit |

Ces trajectoires sont des **phénomènes de distribution** dans l'écosystème des
agents de code : un pack de skills à la mode capte des étoiles sans rien prouver.
Copier leurs tactiques (README multilingue, catalogue gonflé, badge Trendshift)
appliquerait à Alfred une recette dont le carburant — être un accessoire de
Claude Code — n'existe pas ici.

**La classe de référence retenue** est le cohorte des *bibliothèques
d'infrastructure à revendication mesurable*, seule comparable à Alfred :

| Dépôt | Étoiles | Créé | Ce qu'il vend |
|---|---|---|---|
| `headroomlabs-ai/headroom` | 63 k | 07/01/2026 | Compression de contexte — « 60–95 % de tokens en moins, mêmes réponses » |
| `CloakHQ/CloakBrowser` | 29 k | 22/02/2026 | Chromium furtif — « 30/30 tests passed » |
| `tirth8205/code-review-graph` | 27 k | 26/02/2026 | Graphe de code — « benchmarked context reductions » |

C'est ce trio qui sert de référence dans tout ce qui suit.

---

## 2. Ce que font les gagnants (7 motifs)

**M1 — La revendication est un nombre falsifiable, dès la description du dépôt.**
Aucun des trois ne se décrit par sa catégorie. Ils se décrivent par un résultat
vérifiable : « 20 % fewer tokens for coding agents, 60-95 % fewer tokens for
JSON, **same answers** », « 30/30 tests passed ». La revendication contient sa
propre condition de réfutation.

**M2 — La preuve est un tableau, jamais un paragraphe.** Headroom : deux tableaux
dans les 40 premières lignes — économies réelles (avant / après / gain) et
exactitude par benchmark (nom, catégorie, N, baseline, résultat, delta).
Graphify : jugement en aveugle, accord inter-juges 90,6 %, kappa de Cohen 0,81.
La prose sert à commenter le tableau, pas à le remplacer.

**M3 — L'essai sans installation est la première chose exécutable.** Une ligne,
avant toute explication : `uv tool install …`, `uvx …`. Le temps entre l'arrivée
et le premier résultat est traité comme la métrique numéro un.

**M4 — La démo est visuelle et montre le résultat, pas l'installation.** GIF
animé ou capture annotée dans les 30 premières lignes, avec le gain affiché
dessus.

**M5 — Le comparatif nommé est assumé.** Headroom se compare nommément à RTK,
lean-ctx, Compresr, OpenAI Compaction sur 4 axes. Graphify à mem0 et supermemory
avec le même harnais de test. Personne ne dit « d'autres solutions existent ».

**M6 — La surface de recherche est saturée.** 15 à 20 topics, et les noms
d'écosystème (`claude-code`, `cursor`, `mcp`, `langchain`) dans **la description**
autant que dans les topics. Une matrice de compatibilité liste les plateformes
supportées, une par ligne : c'est du référencement autant que de la doc.

**M7 — Le canal possédé et l'étage payant sont dans le README.** Headroom :
Discord dans les badges, section « Headroom for teams » avec adresse mail.
Graphify : waitlist entreprise citée **deux fois** (intro et conclusion).
Nouveauté 2026 : `/llms.txt` en lien de navigation — le dépôt s'adresse aussi
aux agents qui le lisent.

---

## 3. Audit de la vitrine actuelle

État constaté le 2026-07-26 via l'API GitHub sur `adriencr81/Check-Alfred` :

| Élément | État | Motif manqué |
|---|---|---|
| **Description du dépôt** | **vide** | M1, M6 |
| **Topics** | **aucun** | M6 |
| **Releases / tags** | **0** | — |
| **GitHub Pages** | **`has_pages: false`** | — |
| Discussions | désactivées | M7 |
| Étoiles / forks | 1 / 0 | — |
| README | 16 112 caractères, aucune image | M2, M4 |
| Preuve visible au-dessus de la ligne | aucune | M1, M2 |
| Comparatif nommé | présent (bon) | M5 ✅ |
| Essai zéro-install | présent mais à la ligne ~120 | M3 ⚠️ |
| Nom du dépôt | `Check-Alfred` ≠ paquet `alfred-ai` | M6 |

Le fond est **au-dessus** de la moyenne du corpus : le comparatif nommé (§
Positioning) est plus honnête que celui de Headroom, la section « ce qui compte
comme déviation » est d'une précision qu'aucun des trois n'atteint, et l'aveu
« Alfred ne voit que ce que la trace enregistre » est le genre de phrase qui fait
gagner un fil HN. **Le problème n'est pas le contenu, c'est l'ordre et le
format.** Tout est en prose, tout est plat, et les 300 premiers mots ne
contiennent aucun nombre vérifiable.

---

## 4. Les trois fuites critiques (bloquantes avant le launch)

Elles ne relèvent pas du goût. Elles cassent le parcours annoncé dans les posts.

**F1 — La commande héros n'installe rien.** Le README, la landing et tous les
posts prévus reposent sur `uvx alfred-ai demo` et `pip install alfred-ai`. Or le
dépôt n'a **aucun tag**, `release.yml` cible encore **TestPyPI** (« flip the
environment/URL to the real PyPI for the v0.1 launch »), et le nom `alfred-ai`
n'est donc pas réservé par ce projet. Le jour du launch, la première commande que
tape un inconnu échoue — ou installe le paquet de quelqu'un d'autre. C'est déjà
la priorité 1 non cochée du plan de croissance (« réserve le nom ») ; ce plan la
requalifie en **bloquant absolu**, car aucune autre action marketing n'a de
valeur tant qu'elle tient.

**F2 — La landing citée dans tous les posts n'est pas en ligne.** `has_pages`
est `false` : le « Settings → Pages → Source = GitHub Actions » de l'ADR 0029
n'a pas été fait, donc le job `deploy` échoue et
`adriencr81.github.io/Check-Alfred/` ne sert rien. Le README et le CLI (pointeur
teams, ADR 0030 décision 5) pointent tous deux vers ce domaine : **le canal
possédé et le signal payant sont branchés sur une URL morte.** Les deux actions
mainteneur en attente (activer Pages, brancher le formulaire de liste) sont donc
la même urgence.

**F3 — Le nom du dépôt est un artefact, et chaque backlink le grave.** `Check-`
est un préfixe d'outillage, pas une marque : il désaccorde l'URL, le paquet PyPI
(`alfred-ai`), la commande (`alfred`) et le futur org. Le transfert vers l'org
`alfred-ai` est déjà au plan — **il doit précéder le premier post**. Renommer
après le launch, c'est perdre le bénéfice des liens HN, Reddit et newsletters,
qui sont précisément l'actif qu'on va acheter au prix d'un mois de travail.

---

## 5. Le plan

### P0 — Débloquer le parcours (avant tout post)

1. Publier `alfred-ai 0.1.0rc1` sur le vrai PyPI (bascule `release.yml` hors
   TestPyPI, tag `v0.1.0rc1`) — réserve le nom et rend la commande héros vraie.
2. Settings → Pages → Source = GitHub Actions ; vérifier la landing **et**
   `/teams/` en navigation privée.
3. Brancher l'URL du formulaire de liste mail dans `docs/site/index.md`.
4. Transfert vers l'org `alfred-ai`, dépôt renommé `alfred` (redirection GitHub
   automatique depuis l'ancienne URL, donc sans casse).

### P1 — La vitrine elle-même (le cœur de ce plan)

5. **Description + topics** (§6.1) — 2 minutes, plus grand ratio de tout le plan.
6. **Réécrire les 40 premières lignes du README** (§6.2) : revendication
   chiffrée → GIF → commande zéro-install → tableau de preuve. Le reste du README
   descend tel quel : il est bon, il est juste trop tôt.
7. **Le bloc de preuve « ce qu'Alfred refuse de dire »** (§6.3) — l'actif
   différenciant, aujourd'hui absent.
8. **GIF < 15 s montrant la déviation attrapée**, pas l'installation (M4). Le
   plan de croissance le prévoyait comme « GIF de démo » ; la précision compte :
   on filme `alfred watch` qui lève `tool_not_allowed`, pas `pip install`.
9. **Image de partage social** (Settings → Social preview, 1280×640) : la carte
   par défaut de GitHub est générique, or chaque partage HN / Slack / X en
   dépend. Contenu recommandé : les 4 lignes du digest, en monospace, avec les
   `[evt:…]` visibles — la preuve *est* le visuel.
10. **Discussions activées** + 3 « good first issue » ouvertes (déjà au plan).

### P2 — Entretien et composition

11. **`llms.txt` à la racine** (M7) — le public d'Alfred construit des agents ;
    un dépôt lisible par un agent est on-thesis, pas un gadget.
12. **Notes de release comme contenu**, pas comme diff : le `CHANGELOG.md` fait
    21 k caractères, une release qui ne raconte rien ne se partage pas. Une
    release = un « ce qu'Alfred attrape désormais ».
13. **Graphique star-history** en fin de README (M7) une fois passé ~100 étoiles
    — avant, il souligne le vide.
14. **Matrice de compatibilité** en tableau une-ligne-par-plateforme (M6) : la
    table « Plug in your own agent » existe déjà, il suffit de la remonter et de
    la rendre scannable.

---

## 6. Assets prêts à coller

### 6.1 Description et topics

Description (à coller dans Settings, ≤ 350 car.) :

> Accountability layer for AI agents. Turns OpenTelemetry GenAI traces into a
> daily digest where every line is anchored to a trace event ID — mandate
> deviations, cost, escalations. Works with LangGraph, the OpenAI Agents SDK, and
> any OTel collector. No self-reported summaries: a line without a source event
> fails a test.

Topics (20) :

```
ai-agents  llm  opentelemetry  observability  agent-monitoring  ai-governance
python  langgraph  openai-agents  otel  genai  slack  tracing  audit
accountability  compliance  agentops  ai-safety  llmops  evals
```

### 6.2 Les 40 premières lignes du README (structure cible)

```
# Alfred

> Every line of this report is anchored to a trace event ID.
> The ones that aren't, don't ship.

[badges: CI · PyPI · Python · License · Tests]

[GIF — 12 s: an agent calls read_pii, alfred watch flags it, digest in Slack]

## Try it — 20 seconds, no install, no API key, no webhook

    uvx alfred-ai demo

[le bloc de sortie du digest, tel quel — il est déjà excellent]

## What is proven, and how          <- le tableau, AVANT toute prose
```

Trois règles de discipline pour cette zone :

- **Aucun paragraphe avant la première commande exécutable.** « The idea in two
  sentences » et « Status » descendent sous le tableau de preuve.
- **Le statut ne s'excuse pas.** « v0.1 core feature-complete, plus a "Bring Your
  Own Agent" sprint landed » est une phrase de journal de bord. Ce qui se lit :
  « 400 tests · mypy --strict on source *and* tests · Python 3.11–3.14 » — trois
  nombres, en badge.
- **Le mot « manager » reste** : c'est la ligne de fracture avec l'observabilité
  (ADR 0030 décision 1), et aucun des trois concurrents ne l'occupe.

### 6.3 Le bloc différenciant : « What Alfred refuses to say »

À insérer juste après le tableau de preuve. C'est le seul contenu de cette
catégorie qu'aucun concurrent ne peut copier sans réécrire son produit :

```markdown
## What Alfred refuses to say

Most agent reports are a summary the agent wrote about itself. Alfred's can't be:

| Situation | What a self-reported summary says | What Alfred says |
|---|---|---|
| Agent claims it escalated | "Escalated to a human ✅" | Nothing — unless a tool in `escalation_tools` was actually called `[evt:…]` |
| Agent reports its own cost | "Cost: €0.40" | The cost priced from its own token counts, plus `cost_mismatch` if the two disagree |
| Agent answers confidently but wrong | "47 tasks completed ✅" | 47 — and nothing about correctness, because the trace doesn't record it |

The last row is the point: **Alfred does not claim what it cannot anchor.**
Remove the event IDs from a narrated line and the run fails instead of shipping
— `tests/test_narrate_llm.py`.
```

Le troisième rang — l'aveu — est ce qui rend les deux premiers crédibles. C'est
la mécanique de « same answers » chez Headroom : la revendication ne vaut que
par la contrainte qu'elle s'impose.

---

## 7. Ce qu'on ne fait pas

Cohérent avec le backlog négatif (PLAN.md §10) et l'ADR 0030 :

- **Pas de README multilingue.** Coût d'entretien réel, gain nul hors marché
  chinois que le projet ne cible pas.
- **Pas de badge Trendshift / awesome-list farming.** Achète de l'étoile, pas de
  l'installation ; la métrique nord est l'utilisateur récurrent.
- **Pas de Discord** (exclu §10, inchangé). Discussions GitHub suffisent : elles
  sont indexées, elles n'exigent pas de présence quotidienne.
- **Pas de télémétrie déguisée en analytics de vitrine.** L'ADR 0030 décision 7
  tient : ni pixel, ni tracker sur la landing. « Vos traces restent chez vous »
  est un argument d'acquisition — il se paie comptant.
- **Pas de waitlist dans les posts de launch** (ADR 0030 décision 3, inchangé) :
  la page teams capte, elle ne démarche pas.

---

## 8. Critères de succès

Falsifiables, mesurés à J+14 après le premier post :

| Critère | Seuil | Source |
|---|---|---|
| `uvx alfred-ai demo` réussit sur une machine vierge | binaire | test manuel, 3 OS |
| Landing + `/teams/` répondent 200 | binaire | curl |
| Temps arrivée → premier digest lu | < 60 s | chrono, 3 inconnus |
| Part des visiteurs qui atteignent la commande sans scroller | 100 % | structure README |
| Issues `show-your-digest` | ≥ 3 | GitHub |
| Demandes `teams-inquiry` | ≥ 1 | GitHub |

Les quatre premiers sont sous contrôle et se vérifient avant le launch. Les deux
derniers ne le sont pas — ils mesurent le marché, pas la vitrine, et un zéro
n'y conclut rien tant que P0 n'est pas fait (garde-fou §9 : « un tir raté ne
conclut rien »).

---

## 9. Séquence recommandée

```
J-7   P0 (1→4)          publier le rc, activer Pages, liste mail, renommer
J-5   P1 (5, 6, 7)      description, topics, README au-dessus de la ligne
J-3   P1 (8, 9)         GIF, image sociale
J-2   P1 (10)           discussions, good first issues
J-1   relecture à froid : ouvrir le dépôt en navigation privée, chronomètre
J     launch (canaux et calendrier: docs/GROWTH_PLAN_3M.md §1.3)
J+7   P2 (11→14)        llms.txt, notes de release, matrice
```

L'ordre n'est pas négociable sur P0 → P1 : soigner la vitrine d'un dépôt dont la
commande d'installation échoue revient à repeindre une porte fermée à clé.

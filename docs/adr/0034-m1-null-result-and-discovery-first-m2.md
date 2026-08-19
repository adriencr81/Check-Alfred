# 0034 — M1 est un non-événement : canal de pic perdu, M2 repart sur le discovery direct

**Date** : 2026-08-19 · **Statut** : Accepté · **Signé** : Adrien (demande et
arbitrages), Claude Code (audit et rédaction)

## Contexte

Le bilan de launch prévu au 10-14/08 (`docs/GROWTH_PLAN_3M.md` §1.2, dernière
case des semaines du 11/08 et 18/08) n'a pas été fait. Le M1 s'est terminé le
18/08 et le M2 démarre le 19/08 sur un plan qui n'a jamais été confronté au
résultat. Cet ADR fait ce bilan et en tire les conséquences.

### Les chiffres, relevés le 2026-08-19

Ordre de lecture de l'ADR 0032 décision 2 — exécution avant audience.

| Métrique | Cible §1.3 | Réel | Source |
|---|---|---|---|
| Digests partagés publiquement | ≥ 3 | **0** | aucune issue `show-your-digest` |
| Abonnés liste mail | 50 | *non relevé* | back-office Buttondown |
| Contributions d'inconnus | ≥ 5 | **2** | PRs #53, #54 |
| Témoignages écrits | 2-3 | **0** | — |
| Installs pip/semaine | 20-50 | *non relevé* | pypistats.org |
| Stars | 500, plancher 150 | **3** | API GitHub |
| Demandes `teams-inquiry` | ≥ 1 (informatif) | **0** | aucune issue |

Deux contributions de vrais inconnus, le 27/07, mergées le 28/07 :
`KIRA-L001` (#53, pricing DeepSeek) et `sahilsaiyed-oss` (#54, mandat
`support-triage-bot`). Toutes deux en réponse aux issues `good first issue`
#50 et #51. C'est le seul dispositif d'acquisition du plan dont on puisse
prouver qu'il a produit quelque chose.

### Les trois faits qui expliquent ces chiffres

**1. La séquence de launch n'a pas eu lieu.** Le Show HN du mardi 04/08 n'a
pas été posté : **le compte HN est banni**. Aucun document du dépôt n'en porte
trace — PLAN.md §6.3 décrit toujours « Mardi 14h-16h Paris | **Show HN** », le
plan de croissance §1.2 aussi, et l'ADR 0032 raisonne encore sur « la présence
requise 6 h sur HN ». La contrainte était connue au moins depuis le 04/08 ;
elle n'a jamais été écrite.

**2. Aucune case de §1.2 n'est cochée.** Ni l'échauffement des comptes Reddit
(semaine du 21/07), ni la liste des 30 early users, ni les ~15 DM personnalisés,
ni les posts du launch, ni la capture dans le canal possédé. Le plan décrit une
séquence complète dont rien n'atteste l'exécution.

**3. Le travail post-launch existe, hors du dépôt.** Entre le 04/08 et le
12/08 : une stratégie Reddit de niche, un brouillon de réponse, une PR vers
`opentelemetry.io` (fork poussé le 31/07), trois variantes de commentaires
rédigées. Rien n'a été committé, et deux de ces chantiers se sont arrêtés en
attente d'un arbitrage qui n'est pas venu. Le dépôt est silencieux depuis le
05/08.

### Ce que ces chiffres ne disent pas

À 3 stars, le résultat ne mesure ni la demande, ni le positionnement, ni le
produit : il mesure une absence de distribution. Un Show HN qui échoue produit
malgré tout 20-40 stars. Le garde-fou §9 (« un tir raté ne conclut rien,
re-launch en M3 ») a été écrit pour un tir **parti et manqué** ; l'appliquer ici
ferait lire un non-lancement comme un lancement médiocre, donc comme une
situation dont on se remet en attendant. C'est la confusion que cet ADR sert à
empêcher.

## Décisions

**1. Le M1 est enregistré comme un non-événement, pas comme un échec produit.**
Aucune conclusion sur la demande, le positionnement ou le périmètre v0.1 ne peut
être tirée de ces chiffres, et aucune n'est tirée ici. Le seul enseignement
positif est le dispositif `good first issue` : deux inconnus ont contribué sans
qu'aucun canal ne soit ouvert. Il est conservé tel quel.

**2. Le Show HN sort du plan.** Les deux moments de pic de la stratégie en
dépendaient — le mardi de §6.3 et le re-launch M3 de §6.4, prévu lui aussi comme
un Show HN du leaderboard. Les deux perdent leur canal. C'est une contrainte
structurelle, pas un contretemps : elle ne se contourne pas par un compte neuf,
qui est exactement ce que la détection du site cible et ce qui se solde par un
shadowban. La seule voie ouverte est une demande de déblocage à
`hn@ycombinator.com` — coût nul, résultat non garanti, et **le plan ne doit rien
en attendre**.

L'option « replanifier immédiatement un autre canal de pic » a été écartée :
elle reproduirait la faute d'origine — faire reposer la validation sur un
événement unique dont on ne contrôle ni la date ni l'issue.

**3. Le M2 repart sur le discovery direct : 20 conversations.** Objectif :
20 échanges avec des personnes qui font tourner des agents en production, par DM
ou mail, sur une question et non un pitch — « quand ton agent fait une erreur,
comment tu l'apprends aujourd'hui ? ». Deux propriétés en font la seule voie
praticable maintenant :

- **Elle ne demande aucun standing communautaire.** Un DM à un mainteneur ne
  passe ni par un automod, ni par un karma, ni par une modération. C'est la
  seule action du plan dont l'exécution ne dépend que d'Adrien.
- **Elle produit le signal que le launch devait produire.** Dix descriptions
  d'un processus douloureux valident la thèse ; vingt « ça ne nous arrive pas »
  la falsifient. Dans les deux cas le M2 se termine avec une information que
  trois semaines de M1 n'ont pas donnée.

Le vivier est celui déjà écrit en §6.2 et jamais constitué : issues des
frameworks, issues des outils adjacents, auteurs de billets, contributeurs
des PRs #53 et #54.

**4. Le standing communautaire devient une tâche nommée, pas un prérequis
implicite.** Le plan le mentionnait déjà deux fois — « échauffement des comptes
Reddit » (§1.2), « même prérequis d'appartenance que Reddit » (ADR 0032
décision 1) — mais comme condition à remplir avant un launch, donc jamais comme
travail à planifier. Il devient une ligne du M2 : participation sincère et sans
mention d'Alfred, sur le Slack OTel `#sig-ai` et les issues LangGraph. La PR
`opentelemetry.io` déjà ouverte en relève et compte à ce titre.

Ce n'est pas un canal d'acquisition et ne doit pas être mesuré comme tel : c'est
la condition de possibilité de tous les canaux du plan, y compris d'un éventuel
re-launch.

**5. Non-décisions.** Ni prix, ni packaging, ni date pour l'étage payant
(inchangé depuis les ADR 0030 et 0032). Le backlog négatif §10 est inchangé. La
règle produit D5 n'est pas approchée. Le périmètre v0.2 reste piloté par les
issues.

## Conséquences

- `docs/GROWTH_PLAN_3M.md` passe en **révision 1.4** : le bilan M1 ci-dessus est
  reporté en §1.3, les cases non exécutées de §1.2 sont marquées comme telles
  plutôt que laissées ambiguës, et le M2 (§2.2) gagne les 20 conversations en
  priorité 1 et le standing en tâche de fond.
- `PLAN.md` §6.3 et §6.4 : le Show HN est marqué indisponible aux deux endroits
  où il porte un moment de pic. Aucune cible chiffrée n'est modifiée — elles
  n'ont jamais été testées.
- Aucun changement de code, aucun changement de test.
- **Action mainteneur** : relever les deux métriques manquantes du tableau
  (abonnés Buttondown, installs `alfred-ai` sur pypistats.org). Un bilan à deux
  trous se relit mal dans trois mois.
- Ce qui n'est **pas** décidé ici : la suite d'Alfred au-delà du M2. Le dépôt est
  à l'arrêt depuis le 05/08 et l'attention est ailleurs ; cet ADR constate le
  fait et ne le tranche pas. Les 20 conversations sont précisément ce qui donne
  de quoi le trancher sur autre chose qu'une impression.

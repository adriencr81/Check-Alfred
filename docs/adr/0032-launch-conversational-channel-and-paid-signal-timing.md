# 0032 — Créneau conversationnel au launch, ordre des cibles M1, calendrier du signal payant

**Date** : 2026-08-01 · **Statut** : Accepté · **Signé** : Adrien (demande et
arbitrages), Claude Code (audit et rédaction)

## Contexte

Demande utilisateur du 2026-08-01 : audit d'un plan GTM externe (30 jours,
« infiltration » de communautés puis outbound B2B) confronté à la stratégie déjà
actée — PLAN.md §6.0 et §6.3, `docs/GROWTH_PLAN_3M.md` rev 1.2, ADR 0030.

L'essentiel du plan proposé est **déjà livré ou déjà daté** : sa semaine 1 (README
visuel avec GIF, `CONTRIBUTING.md`, dossier `/examples`, dépôt prêt au trafic)
est faite, et sa semaine 2 est la séquence §6.3 fixée au mardi 4 août. L'appliquer
tel quel repousserait le launch d'une semaine pour refaire l'existant. Trois
éléments en revanche ne sont couverts nulle part, et deux contredisent des
décisions actées pour des raisons qui tiennent toujours.

**1. La séquence de launch n'a aucun canal conversationnel.** §6.3 est
intégralement composée de canaux de diffusion : Show HN, Reddit, X, PRs,
newsletters. Un post, un pic, retour à zéro. Or le différenciateur technique
d'Alfred — la consommation de la semconv **GenAI** d'OpenTelemetry et l'ancrage
au niveau *event* — s'énonce sans traduction dans un seul endroit : le Slack
communautaire OpenTelemetry. C'est le public le moins disputé du paysage
(l'observabilité d'agents s'y adresse peu) et celui qui juge le plus vite si la
promesse est réelle. Le vivier « Discords » figure bien dans le sourcing §6.2,
mais il n'a jamais été promu en canal de launch.

**2. Le tableau de cibles M1 ordonne les métriques à l'inverse de leur valeur.**
§1.3 ouvre sur 500 stars — seuil qui correspond en pratique à un top 10 front
page HN, donc à l'issue improbable — et relègue les digests partagés en cinquième
ligne. Le texte sous le tableau dit pourtant l'inverse : « trois personnes qui
montrent une sortie réelle valent plus que trois cents stars ». L'ordre de
lecture contredit l'arbitrage écrit juste en dessous.

**3. Le signal payant n'a pas de motion active, et le plan externe proposait d'y
répondre par un prix.** Le dispositif de l'ADR 0030 (page teams, label
`teams-inquiry`, pointeur stdout) est **passif** par construction. Le plan
proposait de l'activer en semaine 4 par un outbound LinkedIn assorti d'un tarif
annoncé (99 $/mois) et d'une offre hébergée (dashboard, RBAC, SIEM). Les deux
éléments sont à séparer : l'outbound comble un vrai vide, le prix et l'offre
hébergée détruisent des décisions structurantes.

## Décisions

**1. Un créneau conversationnel le vendredi du launch.** Slack communautaire
OpenTelemetry (`#sig-ai`) et Discord LangChain/LangGraph rejoignent la séquence
§6.3, sur le même jour que les PRs d'exemples — le jour « distribution permanente
plutôt que pic », dont ils partagent la logique. Objectif délibérément bas :
**3-5 conversations engagées**, pas un compteur de vues. L'angle y est différent
des autres canaux et ne doit pas être recyclé : sur `#sig-ai`, on n'arrive pas en
annonçant un produit d'accountability, on arrive en consommateur de la semconv
GenAI qui expose ce qu'il en tire et ce qui lui a manqué. Ce public récompense la
contribution au niveau spec ; un pitch produit y est un coût net.

Le prérequis d'appartenance est le même que celui posé pour Reddit en §6.3 (âge
de compte, participation sincère préalable) et relève du même travail que le
sourcing des 30 noms. Un lien froid posté sans historique est au mieux ignoré.

**Contrainte de vocabulaire, verrouillée ici parce qu'elle est intenable à
rattraper** : dans ces salons, on écrit **event ID** (niveau span), jamais
« trace ID ». La différence est exactement celle entre « je te dis dans quelle
session ça s'est passé » et « je te montre l'appel exact » — c'est-à-dire la
totalité de ce qu'Alfred prétend apporter. La formulation de référence est celle
du README (`test_narrate_raises_on_hallucinated_citation`), pas une paraphrase
marketing.

L'option « ouvrir ces canaux dès le mardi » a été écartée : le mardi est saturé
par la présence requise 6 h sur HN, et une même annonce dupliquée le même jour
sur quatre canaux se lit comme du spam par les gens qui fréquentent les deux.

**2. Les digests partagés passent en tête des cibles M1.** Réordonnancement du
tableau §1.3 et du signal de réussite §6.3 : la ligne « digests partagés
publiquement » précède désormais les stars. Aucune cible chiffrée n'est modifiée
— ni les 500 stars, ni le plancher 150, ni le ≥ 3. Ce que change cette décision
est ce qu'on regarde en premier au bilan du 10-14/08, donc ce qu'on conclut d'un
launch médian : un tir à 120 stars et 4 digests réels n'est pas le même événement
qu'un tir à 400 stars et 0 digest, et l'ordre actuel du tableau fait lire ces
deux résultats à l'envers.

L'option « baisser la cible stars à 150 » a été écartée : le seuil de 500 est la
définition d'un succès HN, pas une prévision, et §1.3 le dit déjà. Le problème
n'était pas le chiffre, c'était sa position.

**3. La motion d'audit est ouverte, en M2/M3, et sans prix.** L'outbound
qualifié — proposer à un lead technique de faire tourner Alfred sur ses propres
agents et d'en discuter le résultat — devient une tâche nommée du M3, et non une
tâche de launch. Deux propriétés la rendent compatible avec l'existant :

- **Elle ne touche jamais l'infrastructure du prospect.** La mécanique est celle
  du motion dev-champion (ADR 0030 décision 1) : *il* lance
  `alfred report --html`, *il* transmet le fichier autonome, on le lit ensemble.
  La variante « installez un plugin pour qu'on regarde vos données » a été
  écartée sans hésitation : elle contredit frontalement « your traces never leave
  your infrastructure » (`docs/site/teams.md`), qui est l'argument d'acquisition
  de l'angle r/LocalLLaMA et une propriété du paquet, pas une phrase de vente.
- **Elle est postérieure au launch.** L'ADR 0030 décision 3 avait écarté la
  collecte de leads *pendant* le launch, parce qu'elle se paie sur HN et Reddit.
  Ce raisonnement porte sur la simultanéité, pas sur l'outbound en soi : une
  campagne découplée, un mois après le pic, ne le réactive pas.

**4. Aucun prix, aucun packaging avant J+150.** Le plan externe posait 99 $/mois
en semaine 4. Refusé, et pour une raison de mesure avant d'être une raison de
prix : PLAN.md §8 fait des *demandes de payant spontanées* la ligne qui tranche
entre CDI premium, freelance-runway et fondation. Annoncer un tarif remplace ce
signal par un signal contaminé — à zéro conversion, on ne distingue plus « le
produit n'a pas d'acheteurs » de « le produit n'a pas d'acheteurs **à ce
prix-là** », et c'est précisément la confusion que tout le dispositif de
l'ADR 0030 a été construit pour éviter. Le pont vers le payant reste l'export
dossier de preuve (v0.4, J+150).

**5. Non-décision : le backlog négatif §10 est inchangé.** L'offre « Enterprise »
proposée (dashboard hébergé, multi-tenant, RBAC, intégration SIEM) n'est pas une
grille tarifaire, c'est un pivot produit : le dashboard web est explicitement
dans le backlog négatif assumé, et « zéro infra » est un choix de conception
(SQLite, fichier généré, pas de service à opérer), pas une limite subie. Ouvrir
ce chantier sur un budget de ~1 h/jour se paierait sur la seule chose qui
différencie Alfred. Rien n'est amendé ici.

## Conséquences

- `PLAN.md` §6.3 : la séquence gagne une ligne « vendredi, 2ᵉ créneau »
  (Slack OTel `#sig-ai`, Discord LangChain/LangGraph) et le signal de réussite du
  launch est réordonné, digests partagés en premier. §6.4 gagne la motion d'audit
  en M3. Aucune cible chiffrée n'est touchée.
- `docs/GROWTH_PLAN_3M.md` passe en **révision 1.3** : §1.2 gagne le créneau du
  vendredi et sa contrainte de vocabulaire, §1.3 est réordonné, §3 gagne la
  motion d'audit, et la case « liste mail » de §1.1 est corrigée — le formulaire
  Buttondown est branché dans `docs/site/index.md` depuis le 2026-07-31
  (commit `a7c43ae`), l'action mainteneur bloquante de l'ADR 0030 est donc levée.
  C'était le seul item antérieur au launch encore ouvert.
- Aucun changement de code, aucun changement de test : cet ADR ne décide que des
  canaux, un ordre de lecture et un calendrier. La règle produit D5 et le
  périmètre v0.1 ne sont pas approchés.
- Ce qui n'est **pas** décidé ici : ni prix, ni packaging, ni date pour l'étage
  payant (inchangé depuis l'ADR 0030), ni ajout d'un template d'issue — la
  question de l'instrumentation du funnel (quel framework, quel collecteur) est
  laissée ouverte et sera tranchée sur les issues réelles du launch, pas avant.

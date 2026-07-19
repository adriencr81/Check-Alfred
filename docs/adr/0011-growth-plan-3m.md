# 0011 — Plan de croissance 3 mois (juillet → octobre 2026)

**Date** : 2026-07-19 · **Statut** : Accepté · **Signé** : Adrien (demande), Claude Code (rédaction)

## Contexte

Demande utilisateur du 2026-07-19 : un planning marketing + technique sur
3 mois dont l'objectif unique est de **maximiser le nombre
d'utilisateurs**. PLAN.md v1.1 contient déjà la stratégie (launch §6.3,
post-launch §6.4, métriques §8) mais pas de déclinaison opérationnelle
mois par mois avec cibles intermédiaires et rythme hebdomadaire.

## Décision

Ajouter `docs/GROWTH_PLAN_3M.md` comme **déclinaison opérationnelle** de
PLAN.md §6/§8 sur l'horizon 19 juillet → 19 octobre 2026. Ce document ne
supersède aucune décision actée :

- Les dates (launch 4 août, v0.2 ~J+90, v0.3 ~J+120), les seuils §8, la
  séquence launch §6.3 et le backlog négatif §10 sont repris tels quels.
- Il structure l'horizon en trois goulots successifs du funnel :
  M1 = découverte (launch), M2 = friction d'installation (connecteurs
  v0.2), M3 = boucles récurrentes (leaderboard + re-launch éventuel).
- Seul ajout matériel : le polish d'entonnoir M1 (`pipx`/`uvx`, messages
  d'erreur CLI actionnables, page GitHub Pages) — du polish public, pas
  des features produit, donc compatible avec le gel pré-launch §9/§10.

PLAN.md reçoit un pointeur (une ligne en §6.4) vers ce document pour
préserver la règle « source de vérité unique, pas de plan parallèle ».

## Conséquences

- Le suivi hebdo (vendredi) et la revue mensuelle (dernier vendredi, §8)
  s'exécutent contre les tableaux de cibles M1/M2/M3 du document.
- Tout écart constaté (launch < 100 stars, priorités v0.2 modifiées par
  les issues) se documente par un ADR daté, comme d'habitude.

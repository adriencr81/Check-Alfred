# 0031 — Le déploiement Pages fait la queue au lieu de se percuter

**Date** : 2026-07-27 · **Statut** : Accepté · **Signé** : Adrien (demande),
Claude Code (diagnostic et rédaction)

## Contexte

Le 2026-07-27, quatre PRs Dependabot (#41 à #44) ont été mergées coup sur coup.
Chaque merge sur `main` déclenche le workflow Docs, donc un déploiement Pages.
Trois ont réussi ; le run 9 a échoué :

```
##[error]Failed to create deployment (status: 400) with build version 0a43e86a…
Deployment request failed for 0a43e86a… due to in progress deployment.
Please cancel f409054… first or wait for it to complete.
```

Ce n'est pas un défaut du contenu déployé : le run 9 est entré en collision avec
le déploiement du run 8, encore en cours. Le site publié est resté correct — le
run 10, qui porte le tip de `main`, a réussi.

L'incident est néanmoins à corriger, pour une raison qui n'est pas technique. Ce
dépôt est en préparation de lancement (ADR 0029, 0030) et son argument est la
rigueur vérifiable. Un `main` marqué en rouge pour une course entre deux
déploiements est un faux positif visible depuis la page d'accueil, au moment
précis où des inconnus viennent regarder. Un badge CI ne vaut que si un rouge
veut dire quelque chose.

Le workflow Pages officiel de GitHub porte un bloc `concurrency` par défaut ;
`docs.yml` a été écrit sans (ADR 0029), et la faille ne pouvait pas se voir tant
que Pages n'était pas activé — le job `deploy` échouait de toute façon en 404.

## Décisions

**1. Un groupe de concurrence sur le job `deploy`, pas sur le workflow.** Le
workflow tourne aussi sur `pull_request`, où seul `build` s'exécute (`deploy` est
conditionné à `refs/heads/main`). Un groupe au niveau du workflow sérialiserait
les builds de PR entre eux alors qu'ils ne déploient rien et ne se disputent
aucune ressource. Le groupe est donc porté par le seul job qui accède à
l'unique ressource contendue : le déploiement Pages.

**2. `cancel-in-progress: false`.** Un déploiement déjà en cours va au bout ;
les runs mis en attente derrière lui sont supersédés par le plus récent, qui est
celui qui correspond à `main`. L'option inverse annulerait un déploiement de
production en plein vol — ce que la documentation Pages déconseille — pour ne
rien gagner : c'est le dernier commit qu'on veut publier, et c'est lui qui passe.

**3. La propriété est verrouillée par un test, pas par un commentaire.**
`test_deploy_queues_instead_of_racing_itself` parse `docs.yml` et vérifie les
trois points : le job `deploy` déclare un groupe, `cancel-in-progress` est
`false`, et le workflow n'en porte pas au niveau global. Falsifiabilité
vérifiée : le test échoue quand on retire le bloc, passe quand on le remet.

Le test vit dans `tests/test_docs_site.py` plutôt que dans un fichier neuf : ce
module garde déjà la landing citée dans tous les posts de lancement, et
« la landing se déploie sans faux rouge » relève de la même question que
« la landing existe et ne ment pas ».

## Conséquences

- `.github/workflows/docs.yml` : le job `deploy` gagne
  `concurrency: {group: pages-deploy, cancel-in-progress: false}`.
- `tests/test_docs_site.py` : un test, quatre assertions.
- Effet visible : deux pushes rapprochés sur `main` produisent désormais un
  déploiement et une file d'attente, au lieu d'un déploiement et un rouge. Un
  run superflu peut apparaître en « cancelled » — un état gris qui dit ce qu'il
  s'est passé, contrairement à un échec.
- Ce qui n'est **pas** décidé ici : rien sur le contenu publié, ni sur
  `docs_dir`, ni sur la règle de publication opt-in fichier par fichier posée
  par l'ADR 0029 — elle est inchangée.

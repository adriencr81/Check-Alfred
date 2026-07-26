# 0029 — Chemin zéro-install et landing page : deux décisions de forme

**Date** : 2026-07-26 · **Statut** : Accepté · **Signé** : Adrien (demande), Claude Code (rédaction)

## Contexte

Demande utilisateur du 2026-07-26 : livrer les deux items techniques non cochés
de `GROWTH_PLAN_3M.md` §1.1 priorité 2 (`uvx`/`pipx run` fonctionnels et
documentés ; landing GitHub Pages minimale). Les deux sont **déjà planifiés** et
classés polish d'entonnoir, donc autorisés pendant le gel des features de M1
(PLAN.md §9) — cet ADR ne documente aucun écart au plan. Il existe parce que
chacun a demandé un choix non évident que CONTRIBUTING.md impose de tracer.

## Décision 1 — un second script console, `alfred-ai`

`uvx <nom>` et `pipx run <nom>` résolvent l'exécutable depuis le nom de la
**distribution**, pas depuis les scripts qu'elle déclare. Le paquet s'appelle
`alfred-ai` et ne fournissait que `alfred` : la commande annoncée par le plan,
`uvx alfred-ai demo`, échouait donc sur un paquet parfaitement installé, avec un
message parlant d'exécutable introuvable. Une friction du premier quart d'heure,
exactement la catégorie que la priorité 2 cible.

Deux issues possibles : documenter la forme longue (`uvx --from alfred-ai alfred
demo`, `pipx run --spec alfred-ai alfred demo`), ou ajouter un alias
`alfred-ai = "alfred.cli:main"` à côté de `alfred`. **L'alias est retenu** : la
commande courte est celle qu'on met dans un post de launch et dans le premier
bloc du README, et une forme longue à deux drapeaux se recopie mal. Coût assumé :
deux exécutables installés au lieu d'un. `alfred` reste le nom employé partout
une fois le paquet installé — l'alias n'existe que pour les lanceurs éphémères.

Verrouillé par `tests/test_version.py`, au même titre que la cohérence de
version : supprimer l'alias casse une commande documentée sans casser aucun
environnement déjà installé, c'est-à-dire une panne que seul un nouvel
utilisateur rencontre.

**Vérifié** : `uvx --from <wheel local> alfred-ai demo` produit le digest
attendu — c'est bien la résolution du nom d'exécutable, la partie qui était
cassée, qui est exercée. **Non vérifié** : le chemin `pipx`, dont le binaire
présent dans l'environnement de vérification refuse de démarrer contre l'`uv`
installé (0.8.17 < 0.9.17 requis), quel que soit le backend. Le mécanisme est le
même ; l'affirmation reste à confirmer sur une machine où `pipx` tourne.

## Décision 2 — `docs_dir: docs/site`, pas `docs/`

Le réflexe mkdocs est de pointer `docs_dir` sur `docs/`. Ici ce dossier contient
`GROWTH_PLAN_3M.md` (cibles YC, seuils de revenu, et le critère « la ligne qui
tranche entre CDI premium / freelance-runway / fondation » de PLAN.md §8), la
VCD, et vingt-neuf ADR dont ceux qui décrivent les failles trouvées en pentest.

Le dépôt est public, donc rien de tout cela n'est secret — et c'est précisément
le raisonnement qu'il faut refuser de faire trop vite. Publier ces documents
comme **documentation officielle** sur un site indexé, crawlé, présenté comme la
référence du produit, n'est pas la même exposition que leur présence dans un
dossier de dépôt qu'on atteint en le cherchant. La différence porte sur qui les
lit par accident.

D'où un `docs_dir` dédié (`docs/site/`) où la publication est **opt-in, un
fichier à la fois**. `tests/test_docs_site.py` interdit la régression : il
échoue si `docs_dir` redevient `docs/`, si le plan de croissance apparaît dans
les pages publiées, ou si un dossier `adr/` y atterrit.

Corollaire assumé : la landing redit des affirmations du README (commandes
d'installation, voisins du comparatif), donc elle peut dériver. Deux tests
ancrent ce qui compte — les commandes et la liste des voisins doivent exister
dans les deux fichiers — et rien de plus : la landing a le droit d'être plus
courte et formulée autrement, c'est une landing, pas un miroir.

## Décision 3 — la landing dit qu'elle n'est pas encore publiable

La landing porte les commandes `uvx alfred-ai demo` et `pip install alfred-ai`,
qui ne seront vraies qu'à la publication PyPI. Le workflow déployant depuis
`main`, la page pourrait être en ligne avant le paquet. Elle porte donc une
ligne de statut explicite (« v0.1 targeted for early August 2026 … not on PyPI
yet — build from the repository in the meantime »), à retirer au tag. Même
discipline que la note de PLAN.md §11 sur le quickstart du README : la ligne
d'install ne devient vraie qu'à la publication.

## Conséquences

- La commande la plus courte du launch fonctionne, et un test la garde.
- La landing existe, se construit en `--strict` sur chaque PR, et ne peut pas
  emporter les documents de stratégie par inadvertance.
- **Action mainteneur restante** : Settings → Pages → Source = GitHub Actions.
  Tant qu'elle n'est pas faite, le job `deploy` échoue alors que le job `build`
  protège déjà les PR. Aucun domaine personnalisé n'est configuré (PLAN.md §1
  D3 : domaine non réservé), donc l'URL est `adriencr81.github.io/Check-Alfred`
  — à revoir au transfert vers l'org.

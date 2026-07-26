# 0028 — Durcissement pré-launch : licence, chaîne d'approvisionnement, divulgation, 3.14

**Date** : 2026-07-26 · **Statut** : Accepté · **Signé** : Adrien (demande), Claude Code (rédaction)

## Contexte

Demande utilisateur du 2026-07-26 : point complet de ce qui reste côté technique
avant le launch, hors PyPI. L'audit du repo a trouvé le code en état de sortir
(393 tests, `ruff` et `mypy --strict src/ tests/` verts, wheel installable dans
un environnement vierge, chaîne BYOA rejouée de bout en bout) et **rien à
corriger dans le produit**. Ce qui restait tenait au repo lui-même, pas au
moteur — dont quatre points assez sérieux pour justifier cet ADR plutôt qu'un
commit de ménage.

**1. Le fichier LICENSE était un stub.** 24 lignes de notice abrégée, se
terminant sur son propre TODO : « Replace this abbreviated notice with the full
Apache-2.0 text before v0.1.0 public release. Tracked in issue #1 (to be
created). » L'issue #1 n'a jamais été créée (0 issue ouverte sur le dépôt).
Conséquences vérifiées : l'API GitHub classait le dépôt en `NOASSERTION` /
« Other » pendant que le README affichait un badge Apache-2.0, et
`license-files = ["LICENSE"]` embarquait le stub dans le wheel *et* le sdist.
Pour un produit dont la ligne 2 du README annonce un modèle open-core, la
licence est une affirmation produit : elle ne peut pas être un brouillon.

**2. Aucun canal de divulgation.** Quatre rounds de durcissement livrés
(ADR 0023-0026), un positionnement vers des secteurs régulés (assurance,
finance, santé — PLAN.md §7.1), et aucun `SECURITY.md`. Un chercheur qui trouve
une faille le jour du Show HN n'a que l'issue publique.

**3. Rien ne surveillait les dépendances.** CodeQL scanne le code d'Alfred
chaque lundi, mais aucun mécanisme ne suivait `pyyaml`, les extras connecteurs,
ni les actions épinglées — dont celles de `release.yml`, qui est le workflow
recevant un jeton OIDC de publication.

**4. Python 3.14 était installable et non testé.** `requires-python = ">=3.11"`
autorise pip à installer Alfred sur 3.14 (stable depuis octobre 2025) alors que
la matrice CI s'arrêtait à 3.13. La version qu'un utilisateur rencontre en
premier ne doit pas être celle qu'on n'a jamais exécutée.

## Décisions

**1. Texte Apache-2.0 intégral, récupéré à la source.** Les 202 lignes de
`https://www.apache.org/licenses/LICENSE-2.0.txt`, avec le seul champ
`Copyright [yyyy] [name of copyright owner]` de l'appendice renseigné en
`Copyright 2026 Adrien Deleuil`. Pas de reconstitution de mémoire pour un texte
légal : `curl` puis un `sed` d'un seul champ, ce qui garantit à la fois
l'exactitude et la détection automatique de la licence par GitHub.

**2. `SECURITY.md` bâti sur le modèle de menace réel, pas sur un gabarit.** Le
document nomme explicitement ce qui fait la particularité d'Alfred — **l'agent
audité est l'adversaire**, puisque c'est lui qui écrit la trace lue — et découpe
le périmètre selon les rounds déjà livrés : défaire un contrôle de mandat,
forger du contenu de rapport, casser l'ancrage, faire fuir ce qu'Alfred détient,
arrêter l'auditeur. Le hors-périmètre est aussi important : un agent qui
s'échappe de son instrumentation, un outil qui renvoie du faux avec un statut de
succès, et `chmod` sur Windows sont des **limites documentées**, pas des
vulnérabilités — les qualifier d'avance évite de traiter comme un incident ce
que le produit annonce déjà.

Canal retenu : le *private vulnerability reporting* de GitHub, **pas** une
adresse e-mail. Publier l'adresse personnelle du mainteneur dans un fichier
indexé la livre aux moissonneurs sans rien ajouter à la confidentialité du
signalement. Ce choix suppose une action côté dépôt (Settings → Security →
activer le private reporting) : elle est listée dans le compte-rendu au
mainteneur, sans quoi le fichier renvoie vers une porte fermée.

Délais annoncés : accusé de réception sous 72 h, évaluation sous une semaine,
avec la mention explicite que le projet est maintenu par une personne à temps
partiel. Un SLA que le mainteneur ne peut pas tenir coûte plus de crédibilité
qu'il n'en achète.

**3. Dependabot sur `pip` et `github-actions`, hebdomadaire.** L'outillage de
dev est regroupé en une seule PR (`pytest*`, `ruff`, `mypy`, `types-*`,
`pre-commit`) : ces paquets bougent ensemble et la CI est leur test. Les actions
restent non regroupées — une bump d'action est exactement le changement qu'on
veut lire ligne à ligne quand l'une d'elles détient un jeton de publication.

**4. 3.14 ajouté à la matrice CI plutôt que `requires-python` plafonné.**
Vérification faite avant de décider : les **379 tests hors connecteurs passent
sur 3.14.0rc2**. Les 14 tests connecteurs n'ont pas pu y être exécutés, pour une
raison qu'il faut nommer précisément parce qu'elle est trompeuse : pydantic
2.13.4 (transitif de `[langgraph]` et `[openai-agents]`) appelle
`typing._eval_type(..., prefer_fwd_module=…)`, une API **privée** dont la
signature diffère entre 3.14.0rc2 et 3.14 final. L'échec observé est donc un
artefact du release candidate — le seul interpréteur 3.14 que l'environnement de
vérification pouvait récupérer — et non une preuve que les connecteurs cassent
sur 3.14.

D'où la décision : la matrice passe à `["3.11", "3.12", "3.13", "3.14"]` en
installant `.[dev]` comme les autres versions, et c'est la CI sur un 3.14 final
qui tranche. Aucun job spécial, aucun `--ignore` conditionnel, aucun flag : le
rôle d'une matrice est précisément de découvrir cela sur une PR plutôt que chez
un utilisateur le jour du launch. **Conséquence assumée** : si pydantic ne
supporte effectivement pas 3.14 final, cette PR sort rouge — c'est le résultat
utile, pas un accident. Le classifier `Programming Language :: Python :: 3.14`
est ajouté car il décrit le cœur, dont le support est mesuré ; un
`pip install alfred-ai[langgraph]` sur un 3.14 non supporté échouera par la
résolution des métadonnées de pydantic, ce qui est le comportement correct.

**5. Le VCD est régénéré, pas complété.** `docs/vcd/alfred-v0.1.md` attestait
112 tests et les briques B1-B6 alors que B7-B13, F1-F4 et quatre rounds de
durcissement sont mergés. C'est le document qu'on ouvre pour vérifier une
affirmation — y compris en interview YC (PLAN.md §7.1) — donc un périmètre
périmé n'y est pas un retard de journal, c'est une attestation fausse. La
version 2 ajoute les tableaux de preuve pour B7-B13, F1-F5, les ADR 0022-0027 et
les quatre rounds, remplace les comptages par un relevé réel
(`pytest --collect-only -q`, 393 cas pour 364 définitions), et **ferme une limite
ouverte** : le wheel est désormais vérifié installé dans un environnement
vierge, hors du repo.

## Ce qui n'est pas décidé ici

- **Le trim du sdist.** `PLAN.md`, `docs/GROWTH_PLAN_3M.md`, `CLAUDE.md` et
  `.claude/` partent dans `alfred_ai-0.1.0.tar.gz` (hatchling inclut tout par
  défaut). Le dépôt étant public, ce n'est pas une fuite ; mais un
  `pip download` livre les cibles YC, les seuils de revenu et le critère de
  décision CDI / fondation de §8. Arbitrage build-in-public qui appartient au
  mainteneur, pas à cet ADR.
- **Le transfert vers l'org `alfred-ai` et le domaine** (PLAN.md §1 D3, §11) :
  action mainteneur, à faire avant le tag pour que les stars s'accumulent à
  l'adresse définitive. Les URLs de ce commit sont normalisées sur
  `adriencr81/Check-Alfred` (la casse divergeait entre README et
  `pyproject.toml`) précisément pour que ce transfert soit un remplacement
  mécanique.
- **La répétition de release et la publication** (ADR 0016) : `release.yml`
  n'a jamais tourné une seule fois — zéro run, zéro tag — donc l'échange OIDC
  reste non prouvé. Hors périmètre de la demande (« à part PyPI »), mais c'est
  le dernier verrou technique du launch.
- **Les 3 « good first issue »** (DoD B6, PLAN.md §11) : le label existe, aucune
  issue n'est ouverte. Action mainteneur.

## Conséquences

- Le dépôt annonce la même licence dans le badge, les métadonnées du paquet et
  le fichier — et GitHub la détecte.
- Un signalement de faille a un chemin privé, et le périmètre annoncé évite de
  débattre au moment où ça compte.
- La CI dira si 3.14 est un support réel ou une déclaration.
- Le VCD redevient utilisable comme pièce de vérification.

# 0016 — Publication PyPI via Trusted Publishing, TestPyPI d'abord

**Date** : 2026-07-21 · **Statut** : Accepté

## Contexte

Toute la doc promet `pip install alfred-ai`, mais rien n'était packagé pour
publication : `pyproject.toml` portait des URLs erronées (`github.com/alfred-ai/
alfred`, qui n'est pas le repo) et un champ `license` au format déprécié qui
faisait échouer `twine check`. Aucun workflow de release n'existait. C'est le
verrou d'adoption client n°1 : sans PyPI, il n'y a qu'une évaluation depuis un
clone (`pip install -e`), pas d'usage réel. La v0.1 est visée pour début août ;
il faut préparer la publication sans la déclencher prématurément ni risquer le
nom `alfred-ai` (libre, vérifié : 404 sur PyPI au 2026-07-21).

## Décisions

**1. Trusted Publishing (OIDC), pas de token stocké.** GitHub Actions prouve
l'identité du repo à PyPI via OIDC ; aucun mot de passe ni token d'API dans le
repo ou dans les secrets GitHub. Échange court et scoppé, recommandation
officielle PyPI. Le workflow `release.yml` porte `permissions: id-token: write`
et délègue à `pypa/gh-action-pypi-publish`.

**2. TestPyPI d'abord, bascule vers PyPI réel en une ligne.** Une publication
est irréversible (nom réservé à vie, une version ne se ré-uploade jamais). On
répète donc la release sur TestPyPI — index jetable — avant de brûler le nom
réel. Le passage au vrai PyPI est documenté dans `docs/RELEASING.md` : ajouter
un pending publisher sur pypi.org, retirer `repository-url`, passer la version
de `.dev` à `0.1.0`, pousser le tag. Décision utilisateur (calendrier août).

**3. Métadonnées modernisées (PEP 639).** `license = "Apache-2.0"` (expression
SPDX) + `license-files = ["LICENSE"]`, et suppression du classifier de licence
redondant. URLs corrigées vers `adriencr81/Check-Alfred`. `twine check` passe
(validé en venv propre ; le `packaging` système 24.0, non désinstallable dans
l'env de dev, ne reconnaît pas encore les champs Metadata 2.4 — non bloquant,
la CI utilise une version récente).

**4. Déclencheurs : `workflow_dispatch` + tag `v*`.** Le bouton manuel sert au
dry-run TestPyPI ; le tag sert la release réelle. Le job `publish` dépend d'un
job `build` qui `twine check` d'abord — pas de publication sur un artefact
invalide.

## Conséquences

- `pyproject.toml` : license SPDX + `license-files`, URLs corrigées, classifier
  de licence retiré. Version inchangée (`0.1.0.dev0`) pour le dry-run TestPyPI.
- Nouveau `.github/workflows/release.yml` (build + `twine check` + publish
  TestPyPI via OIDC, environnement `testpypi`).
- Nouveau `docs/RELEASING.md` : runbook des étapes manuelles côté mainteneur
  (pending publisher, vérif d'install, passage au PyPI réel).
- `pyproject.toml` gagne aucune dépendance de run ; `build`/`twine` restent des
  outils CI, pas des deps du paquet.
- Action requise hors dépôt (non automatisable par l'agent) : configurer le
  pending publisher sur test.pypi.org puis lancer le workflow.

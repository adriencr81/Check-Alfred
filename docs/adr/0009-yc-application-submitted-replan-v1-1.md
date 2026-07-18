# 0009 — Candidature YC déposée : re-planification (PLAN.md v1.0 → v1.1)

**Date** : 2026-07-18 · **Statut** : Accepté · **Signé** : Adrien (décision), Claude Code (audit + rédaction)

## Contexte

Deux faits nouveaux rendent PLAN.md v1.0 (daté du 2026-07-15) partiellement
caduc, trois jours seulement après sa signature :

**1. La candidature YC a été déposée le 2026-07-18** (décision utilisateur).
Cela contredit la décision D2 de PLAN.md v1.0 (« cible unique = candidature
sérieuse 2027, pas de candidature-exercice Fall 2026 »). D2 est donc
**supersédée**. Le batch visé n'a pas été précisé dans la demande ; le plan
v1.1 est par conséquent calé sur des **événements** (invitation à interview,
demande de métriques) et non sur des dates de batch. Hypothèse de travail :
une réponse YC peut arriver sous 2 à 6 semaines — toute la traction
démontrable doit donc exister *avant* ce moment, pas au 12 décembre 2026.

**2. Les 6 briques v0.1 sont terminées à J+3 au lieu de J+45.** Audit
d'état exécuté ce jour sur `main` :

```
$ python3 -m pytest -q          → 112 passed
$ ruff check .                  → All checks passed!
$ python3 -m mypy --strict src/ → Success: no issues found in 24 source files
$ alfred demo                   → digest réel, 4 lignes, toutes ancrées [evt:…]
CI GitHub Actions (main)        → success (2026-07-18)
CodeQL (main)                   → success (2026-07-18)
Issues ouvertes                 → 0
PyPI `alfred-ai`                → 404 (nom encore libre, PAS réservé)
```

Le goulot d'étranglement n'est plus le build : c'est tout ce qui est
**public** — la checklist manuelle laissée ouverte par l'ADR 0008
(publication PyPI, tag `v0.1.0`, GIF, 3 « good first issue », org/domaine)
plus la constitution de la liste d'early users (§6.2), qui n'a pas commencé.

## Décisions

**1. D2 supersédée — la candidature déposée devient un jalon du plan.**
Le dossier YC n'attend plus J+150 : chaque semaine à partir de maintenant
doit améliorer ce qu'un partner verrait en ouvrant le repo ou en lançant
`pip install alfred-ai`. Le narratif §7.1 (« le paquet pip a prouvé la
demande ») reste la cible ; seule l'échéance change.

**2. Le launch est avancé du 30 août au mardi 4 août 2026 (J+20).**
Justification : le produit passe déjà le « test 5 minutes » (DoD B6) ; le
seul actif qui se construit en attendant est la liste d'early users, et
deux semaines suffisent pour une version compressée (15 noms au lieu de
30, DM à J+15 au lieu de J+35). Attendre le 30 août n'ajouterait que du
risque (nom PyPI squattable, concurrents, candidature YC évaluée sur un
repo sans traction). La séquence 5 jours de §6.3 (HN → Reddit → X →
LinkedIn → newsletters) est conservée telle quelle, translatée au 4 août.

**3. Sprint S0 « tout ce qui est public » sous 72 h (18–21 juillet)** —
reprend la checklist ADR 0008 restée ouverte, dans cet ordre :
1. Réserver le nom : publier `alfred-ai 0.1.0rc1` sur PyPI (vérifié libre
   le 2026-07-18 — chaque jour d'attente est un risque de squat).
2. Créer l'org GitHub `alfred-ai`, y transférer le repo (les redirections
   GitHub préservent clones et liens ; à faire AVANT le launch pour que
   les stars s'accumulent à l'adresse définitive). Réserver le domaine.
3. Enregistrer le GIF de démo (< 15 s) et l'insérer en haut du README.
4. Ouvrir les 3 « good first issue ».
5. Basculer le quickstart README sur `pip install alfred-ai`.
6. Tag `v0.1.0` + publication PyPI finale une fois 1–5 faits.

**4. Piste parallèle « YC-readiness » (indépendante du launch)** :
vidéo fondateur 1 min (thèse en 3 phrases + légitimité vérification
systèmes critiques), screencast `alfred demo` 60 s, réponse « why now »
rédigée, et un suivi métriques hebdomadaire (stars, pypistats, issues
externes) démarré dès la publication PyPI — la courbe d'installs de §7.2
a besoin d'un point zéro daté.

**5. Les jalons chiffrés glissent de J+45 → J+20.** Le signal de réussite
du launch (≥ 500 stars, ≥ 20 installs, ≥ 5 issues externes) s'évalue au
~10 août ; la revue J+90 de §8 devient une revue au 1er septembre. Les
seuils eux-mêmes ne changent pas — seule la date change.

**6. Ce qui ne change PAS.** La règle produit D5 (ancrage event ID), le
backlog négatif §10 (aucune feature ajoutée pré-launch), la cadence v0.2
→ v0.4 (§6.4) priorisée par les issues, et la ligne de décision §8
(demandes de payant spontanées, pas stars).

## Conséquences

- PLAN.md passe en v1.1 : D2 marquée supersédée (renvoi à ce document),
  §5 marqué livré, §6.3 et §11 recalés. Les sections §2, §3, §9, §10
  restent inchangées.
- La checklist manuelle de l'ADR 0008 est absorbée par le sprint S0
  ci-dessus et cesse d'être une liste flottante.
- Risque assumé : pre-launch compressé = liste d'early users plus courte
  (≈ 15 noms). Garde-fou existant §9 (« un HN raté se retente à 3 mois
  sous un autre angle ») inchangé.

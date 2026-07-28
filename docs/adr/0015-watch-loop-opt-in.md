# 0015 — `alfred watch --loop` : mode continu opt-in (amende l'ADR 0007 §1)

**Date** : 2026-07-21 · **Statut** : Accepté · **Amende** : ADR 0007 §1

## Contexte

L'ADR 0007 §1 a tranché — avec l'utilisateur — que `alfred watch` fait une
**passe unique** et se relance via cron ; un vrai « watch » continu était
déclaré « hors scope v0.1 ». Depuis, l'objectif produit s'est resserré sur la
facilité d'usage client : passer de « installé » à « digest récurrent » sans
bricolage. La ligne cron (`alfred schedule`, ADR 0007 §1 rendu concret) couvre
le cas nominal, mais un client qui déploie Alfred dans un **conteneur ou une CI
sans cron** n'a aucun moyen intégré de rendre le digest récurrent. Décision
prise avec le owner : offrir les deux — cron par défaut, `--loop` en option.

## Décision

**`alfred watch` gagne un opt-in `--loop` ; la passe unique reste le défaut.**

1. **Sans `--loop`, rien ne change.** `watch_once` demeure le primitive intact,
   invoqué exactement comme avant. La garantie testabilité de l'ADR 0007 §1
   (« aucun mock de temps ni de signal d'arrêt ») est préservée pour le chemin
   par défaut, et tous les tests existants de `test_watch.py` restent valides
   tels quels.

2. **`--loop` est un wrapper mince et injectable.** Nouvelle fonction
   `alfred.watch.watch_loop(...)` qui appelle `watch_once` en boucle, livre les
   digests via un callback `on_digests`, puis dort `interval_s` secondes. Les
   dépendances au temps sont **injectées** — `sleep=time.sleep` et un
   `max_passes` optionnel — pour rester testable sans horloge réelle ni signal,
   dans le même esprit que l'ADR 0007 §1 (et que les `Transport` fakes des
   briques 4/5). En production, `max_passes=None` boucle indéfiniment ;
   `KeyboardInterrupt` (Ctrl-C) sort proprement, géré dans le CLI.

3. **Aucun digest ré-émis entre passes.** `watch_loop` réutilise la
   déduplication existante `.alfred/seen.json` (`_load_seen`/`_save_seen`) via
   `watch_once` : un fichier déjà ingéré n'est jamais reconsidéré, donc la
   boucle ne re-livre pas un digest tant qu'aucun nouveau fichier trace
   n'arrive. L'état machine reste séparé de la config (ADR 0007 §2).

## Conséquences

- `src/alfred/watch.py` : ajout de `watch_loop` ; `watch_once` inchangé.
- `src/alfred/cli.py` : `watch` gagne `--loop` et `--interval` (secondes,
  défaut 60) ; la livraison stdout + Slack est factorisée dans un helper
  réutilisé par la passe unique et la boucle.
- `pyproject.toml` inchangé : `time` est stdlib, aucune dépendance ajoutée.
- Tests falsifiables : `tests/test_watch.py` (boucle avec `sleep` factice +
  `max_passes`), `tests/test_cli.py`. Le chemin par défaut reste couvert par
  les tests existants, non modifiés.
- La recommandation reste **cron via `alfred schedule`** (zéro process qui
  tourne) ; `--loop` est le repli pour les environnements sans cron.

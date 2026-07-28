# 0017 — Alertes de déviation en temps réel (opt-in `alfred watch --alerts`)

**Date** : 2026-07-22 · **Statut** : Accepté · **Complète** : ADR 0007, ADR 0012, ADR 0015

## Contexte

Alfred livre un **digest quotidien** : un manager découvre donc une déviation
critique — un remboursement de 250 € au-dessus du cap, un budget explosé, une
escalade ratée — au mieux le lendemain matin. Pour un produit qui vend la
*responsabilité* (« every line anchored to a trace event ID »), c'est le plus
gros trou d'expérience : la valeur d'une alerte décroît avec le temps écoulé
depuis l'événement. Le moteur (`alfred.mandate.engine`) calcule déjà chaque
`Deviation` ancrée sur son event ID ; ce qui manque n'est pas la détection mais
un canal *push* immédiat, distinct de la revue de routine.

C'est la première des cinq features priorisées post-launch (PLAN.md §13).

## Décisions

**1. Opt-in `--alerts` sur `watch` ; le défaut ne change pas.** Même posture
que `--loop` (ADR 0015) : sans le flag, `watch` se comporte à l'identique et
tous les tests existants restent valides. Couplé à `--loop --interval`, `--alerts`
devient une surveillance quasi temps réel (une alerte par passe qui trouve une
nouvelle déviation) ; en passe unique, il alerte une fois par exécution.

**2. On alerte sur *chaque* déviation — pas de seuil de sévérité.** Ajouter un
filtre `severity`/`alert_on` serait de la config pour un besoin hypothétique
(CLAUDE.md : « pas de flag pour un besoin hypothétique »). La déduplication
existante (`.alfred/seen.json`) garantit déjà qu'une même déviation n'est jamais
ré-alertée entre passes. Un filtrage par type/sévérité est **différé jusqu'à ce
qu'un utilisateur le demande**.

**3. L'alerte est un canal Slack.** Le digest stdout affiche déjà ses déviations ;
une « alerte » stdout serait redondante. `--alerts` sans webhook configuré n'est
donc pas un no-op silencieux : `watch` émet un avertissement clair sur stderr et
continue (le digest reste livré). Fail loudly, comme le reste du code de livraison.

**4. Payload d'alerte dédié, ancrage hérité.** `build_alert_payload(digest)`
produit un Block Kit ciblé : en-tête 🚨 distinct, la **même** section
d'avertissement que le digest (`_deviation_section`, réutilisée — zéro
duplication), et un bloc contexte qui liste les event IDs fautifs. La garantie
D5 (chaque affirmation ancrée sur un event ID réel) est donc héritée, pas
réimplémentée. Construire une alerte sans déviation est un bug appelant :
`build_alert_payload` lève `ValueError` plutôt que de poster une alarme vide.

**5. Réutilisation du transport prouvé.** `send_alert` partage
`HTTPRequest`/`Transport`/`_urllib_transport`/`DeliverError` avec `send` via un
helper `_post` privé — aucune nouvelle dépendance, aucun nouveau chemin réseau,
tests sans réseau réel (fake `Transport`), exactement comme les briques 4/5.

## Conséquences

- `src/alfred/deliver/slack.py` : ajout de `build_alert_payload`, `send_alert`,
  `_alert_evidence_context` et du helper `_post` (factorisé depuis `send`).
- `src/alfred/cli.py` : `watch` gagne `--alerts` ; `_deliver` gagne un paramètre
  `alerts` (par défaut `False`) et pousse une alerte quand la passe a livré des
  déviations et qu'un webhook est configuré ; avertissement stderr si `--alerts`
  sans webhook.
- `pyproject.toml` inchangé (aucune dépendance ajoutée).
- Tests falsifiables : `tests/test_deliver_slack.py` (payload d'alerte, garde
  `ValueError`, Block Kit valide, `send_alert` poste le bon corps),
  `tests/test_cli.py` (déviation → une alerte ; sans `--alerts` → aucune ; sans
  webhook → avertissement). Chemin par défaut couvert par les tests existants.
- La recommandation de cadence reste inchangée : cron via `alfred schedule` pour
  le digest quotidien ; `--alerts` (idéalement avec `--loop`) pour le push
  immédiat des déviations.

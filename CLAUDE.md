# Alfred — accountability layer for AI employees

## Ce qu'est ce projet
Paquet pip qui ingère des traces d'agents (OpenTelemetry, semconv GenAI),
les confronte à un mandat déclaré (YAML), et poste un daily digest dans Slack.

## Règle produit ABSOLUE (non négociable)
Chaque affirmation d'un rapport DOIT être calculée depuis un événement de
trace identifiable (event ID). Le LLM ne sert QU'À la mise en langage.
Aucun résumé auto-déclaré. Si une implémentation viole ça : STOP, replanifier.

## Stack & conventions
- Python 3.11+, typage strict (mypy --strict), ruff pour lint/format
- SQLite pour le trace store (zéro infra en v0.1)
- pytest ; TOUT nouveau comportement a d'abord son test falsifiable
- Pas de dépendance lourde sans justification écrite dans le plan

## Workflow imposé
- Toute tâche multi-fichiers commence en plan mode, jamais en édition directe
- Si l'exécution diverge du plan approuvé : stop et re-planifier
- Preuve exigée à chaque fin de tâche : sortie pytest + commande exécutée
- Un commit par brique cohérente, message en anglais impératif

## Discipline d'exécution
- Aucune supposition silencieuse : si une consigne est ambiguë, demander
  plutôt que deviner (mandat, seuil de déviation, format de digest, etc.)
- Simplicité d'abord : le code minimal qui satisfait le test falsifiable —
  pas d'abstraction, de config ou de flag pour un besoin hypothétique
- Modifications chirurgicales : ne toucher que le code lié à la tâche en
  cours ; aucun refactor ou renommage orthogonal dans le même commit
- Objectifs vérifiables : traduire toute demande floue en critère de succès
  testable avant d'écrire du code

## Commandes
- Tests : pytest -q
- Lint : ruff check . && mypy --strict src/
- Démo locale : alfred demo (agent factice → daily en stdout)
- Setup hooks (une fois) : pre-commit install

## Vocabulaire
mandate = YAML déclaratif ; trace event = span OTel normalisé ;
deviation = action hors mandat ; digest = rapport quotidien calculé

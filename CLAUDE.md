# Alfred — accountability layer for AI employees

## Ce qu'est ce projet
Paquet pip qui ingère des traces d'agents (OpenTelemetry, semconv GenAI),
les confronte à un mandat déclaré (YAML), et poste un daily digest dans Slack.

## État courant — LIRE AVANT TOUTE TÂCHE GTM (au 2026-08-19)

**Le produit est livré et public** ; ce qui bloque est la distribution, pas le
code. Ne pas proposer de features tant que ce qui suit n'est pas résolu.

- **Le launch du 04/08 n'a pas eu lieu.** Le compte Hacker News est **banni** :
  le Show HN est définitivement hors du plan, et le re-launch M3 qui en
  dépendait aussi. Ne jamais replanifier un Show HN. Ne jamais suggérer un
  compte neuf — c'est ce que la détection du site cible.
- **Résultat M1 = non-événement**, pas échec produit : 3 stars, 0 digest
  partagé, 2 contributions d'inconnus (PRs #53, #54). À 3 stars on mesure une
  absence de distribution. Le garde-fou §9 de PLAN.md ne s'applique pas — il a
  été écrit pour un tir parti et manqué. Voir `docs/adr/0034-*`.
- **Aucun standing communautaire.** Reddit, Slack OTel, Discord : tous exigent
  une ancienneté que le compte n'a pas. Toute stratégie qui suppose de poster
  quelque part est bloquée à la racine tant que ce n'est pas construit.
- **Priorité 1 du M2 : les 20 conversations de discovery direct.** Vivier
  constitué et prêt : `docs/discovery/vivier-m2.md`. Contact le plus proche du
  produit : `AAH20` sur LangGraph. Critère fixé d'avance : ≥ 10/20 décrivent une
  douleur réelle → la thèse tient ; sinon on acte l'inverse.
- **Deux métriques jamais relevées** : abonnés Buttondown, installs
  `alfred-ai` sur pypistats.org.
- Le dépôt est à l'arrêt depuis le 05/08, l'attention est sur un autre projet
  (`adriencr81/backfire`). Ce fait est constaté, pas tranché.

**Règle de mémoire, apprise à la dure** : une décision qui n'est pas écrite dans
ce dépôt n'existe pas. La stratégie post-ban a été discutée dans au moins trois
sessions entre le 29/07 et le 12/08 et n'a jamais été committée — deux semaines
plus tard, le plan opérationnel décrivait encore un canal impossible. Toute
session qui décide quelque chose de GTM finit par un ADR committé, **sans
exception**, même si la décision est « on ne fait rien ».

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
- Lint : ruff check . && mypy --strict src/ tests/
- Démo locale : alfred demo (agent factice → daily en stdout)
- Setup hooks (une fois) : pre-commit install

## Vocabulaire
mandate = YAML déclaratif ; trace event = span OTel normalisé ;
deviation = action hors mandat ; digest = rapport quotidien calculé

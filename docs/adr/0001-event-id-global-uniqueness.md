# 0001 — `event_id` traité comme globalement unique en v0.1

**Date** : 2026-07-16 · **Statut** : Accepté (risque documenté) · **Signé** : Claude Code (Brique 1)

## Contexte

`PLAN.md §3` pose l'invariant : « `TraceEvent` est immuable et porte toujours
un `event_id` stable et unique. » `TraceStore` (Brique 1) implémente
`event_id` = le `spanId` OTel, utilisé comme `PRIMARY KEY` SQLite global (pas
scopé par `trace_id`), et `get(event_id)` ne prend qu'un seul paramètre.

Or la spécification OTel ne garantit l'unicité d'un `spanId` (identifiant
aléatoire 64 bits) qu'*au sein d'une trace* — pas globalement. Deux traces
distinctes peuvent en théorie produire le même `spanId`. La review senior
IVVQ sur la Brique 1 a signalé ce point comme MAJOR : en cas de collision,
`INSERT OR REPLACE` écraserait silencieusement une ancre d'audit existante,
ce qui menace directement la thèse produit (chaque affirmation d'un rapport
ancrée sur un `event_id` fiable).

## Décision

Pour v0.1, on **accepte** l'hypothèse d'unicité globale de `event_id`, sans
la faire respecter par construction (pas de clé composite `(trace_id,
event_id)`). Justification :

- L'API de `TraceStore.get()` / les tests falsifiables de la Brique 1
  (`tests/test_trace_store.py`) sont déjà figés sur la signature
  `get(event_id: EventId) -> TraceEvent | None`, sans `trace_id`. Passer à
  une clé composite casserait ce contrat et nécessiterait de relire toute
  la chaîne (report, narrate) qui cite un `event_id` seul.
- La probabilité de collision d'un `spanId` 64 bits aléatoire, dans le
  volume de traces v0.1 (agents mono-tenant, watch de fichiers OTLP), est
  négligeable en pratique — c'est l'hypothèse implicite de la plupart des
  backends d'observabilité OTel (Jaeger, Tempo).

## Conséquences

- Risque résiduel documenté : en cas de collision improbable, une ancre est
  silencieusement écrasée (`TraceStore.put` docstring renvoie ici).
- **À revisiter avant B2/B3** si le volume de traces ingérées augmente
  significativement, ou si un client rapporte une collision réelle : migrer
  vers une clé composite `(trace_id, event_id)` et faire évoluer l'API en
  conséquence (déviation qui devra elle-même être actée par une nouvelle
  entrée ADR).

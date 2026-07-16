# 0002 — Corrections de bugs dans le squelette bootstrap de la Brique 1

**Date** : 2026-07-16 · **Statut** : Accepté · **Signé** : Claude Code (Brique 1)

## Contexte

Le commit `4c6d114` (bootstrap) posait le squelette de la Brique 1 : modèle,
stubs `NotImplementedError`, tests déjà écrits, fixture OTLP. En implémentant
les stubs (commit `08570a3`), deux incohérences pré-existantes dans ce
squelette ont bloqué la suite de tests avant même d'atteindre le code à
écrire :

1. `tests/test_trace_store.py` importait `TraceStore` depuis
   `alfred.trace.model`, alors que la classe est définie dans
   `alfred.trace.store` (erreur de collection pytest).
2. `tests/fixtures/otlp_sample.json` portait des `startTimeUnixNano` /
   `endTimeUnixNano` qui résolvaient à 2025-08-30, alors que
   `tests/test_trace_ingest.py::test_ingest_normalizes_timestamps_utc`
   attend explicitement `2026-08-29T21:00:00Z` — cohérent avec le calendrier
   du launch (`PLAN.md`, ~30 août 2026).

## Décision

Dans les deux cas, le test falsifiable fait foi (c'est le contrat, par
construction du projet — `CLAUDE.md` : « TOUT nouveau comportement a
d'abord son test falsifiable »). Corrections appliquées :

1. Import fixé vers `alfred.trace.store.TraceStore` — une seule lecture
   possible, aucune ambiguïté.
2. Les trois timestamps de spans (root/chat/tool) de la fixture recalculés
   pour atterrir sur `2026-08-29T21:00:00Z`, en préservant les offsets
   relatifs originaux entre spans (root +12s, chat +1s→+4s depuis le
   root, tool +5s→+6.5s depuis le root).

## Conséquences

Aucune régression : les deux corrections touchent des artefacts de test/
fixture, pas la logique métier. `pytest -q` : 18/18 avant rework, 21/21
après ajout des tests `.kind` (voir `0003-span-kind-classification.md`).

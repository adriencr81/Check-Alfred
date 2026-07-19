# ADR 0012 — Identité des fichiers vus par watch + casse des IDs à l'ingestion

**Date** : 2026-07-19 · **Statut** : accepté ·
**Contexte** : `docs/plan-simplification-prod.md` (brique S6, bugs B6-B7).

## Décisions

1. **`seen.json` enregistre `nom:taille:mtime_ns`**, plus le nom seul.
   Le nom seul confondait deux fichiers homonymes issus de dossiers
   différents et ne réingérait jamais un fichier réécrit avec du nouveau
   contenu. Effet secondaire voulu : un fichier mis en quarantaine (ADR
   0011) qui est corrigé sur disque change de taille/mtime et est
   rescanné. Migration : les entrées à l'ancien format ne matchent plus,
   donc les fichiers déjà vus sont rescannés une fois après mise à jour —
   sans double-comptage en base (`INSERT OR REPLACE` idempotent), au prix
   d'une re-livraison ponctuelle du digest. Accepté en v0.x.
2. **`spanId`/`traceId`/`parentSpanId` sont normalisés en minuscules à
   l'ingestion.** La docstring d'`ingest_otlp_json` promettait « hex,
   lowercased » sans que le code le fasse : deux exporteurs écrivant le
   même span en casses différentes auraient produit deux anchors
   distincts. Le code tient désormais le contrat documenté.

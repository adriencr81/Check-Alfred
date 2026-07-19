# 0012 — Digest Slack en Block Kit natif, IDs de preuve tronqués à l'affichage

**Date** : 2026-07-19 · **Statut** : Accepté · **Signé** : Claude Code

## Contexte

La première démo Slack réelle (refund-bot-v3, brique 7, vrais span IDs OTel
de 16 caractères hex) a révélé deux défauts du payload de la brique 5 :

1. **La preuve noyait les faits.** Six event IDs complets sur la ligne Cost
   s'étalaient sur deux lignes ; l'ADR 0007 avait enveloppé le texte de
   `render` dans un unique bloc de code, format pensé avec les IDs courts
   des fixtures, pas avec de vrais IDs OTel.
2. **La déviation — le moment clé du produit — était invisible.** Dernière
   ligne d'un pavé monospace gris, sans hiérarchie, avec en prime un titre
   dupliqué (header Block Kit + première ligne du texte rendu).

## Décisions

**1. Le payload Slack utilise des blocs natifs, remplaçant la décision
« une seule source de vérité textuelle » de l'ADR 0007 pour ce sink.**
Structure : `header` (titre) → `section.fields` (un champ par ligne du
digest) → `section` d'avertissement ⚠️ dédiée aux déviations (uniquement
s'il y en a) → bloc `context` portant les IDs de preuve. Un champ
top-level `text` sert de fallback de notification (« … — 1 deviation » /
« … — all clear »), absent jusqu'ici. La cohérence entre sinks est
préservée autrement : `slack.py` réutilise `LABELS`, `format_value` et
`format_sources` de `alfred.report.render` — libellés, formatage des
valeurs et affichage de preuve restent identiques, seule la mise en page
diffère.

**2. Les event IDs sont tronqués et échantillonnés à l'affichage, jamais
dans les données.** `format_sources` affiche au plus 3 IDs par ligne puis
` +N`, et tronque tout ID de plus de 12 caractères à un préfixe de 8
(`e69a993566e99bd0` → `e69a9935…`). Le seuil de 12 laisse intacts les IDs
lisibles des démos (`d0a`, `demo-1-task`). La règle produit absolue
(chaque affirmation calculée depuis un event ID identifiable) porte sur le
calcul : `Line.sources` et `Deviation.event_ids` conservent tous les IDs
complets, et la vérification d'ancrage de la brique 4 (`narrate/llm.py`)
cite depuis `Line.sources`, pas depuis le rendu — non affectée. Un préfixe
de 8 hex suffit à retrouver l'événement dans le trace store.

**3. Le validateur Block Kit de test est étendu, pas remplacé.**
`tests/_block_kit.py` couvre désormais `section.fields` (max 10, chacun
≤ 2000 chars) et `context.elements` (max 10, chacun ≤ 2000 chars), limites
reprises de la doc publique Slack dans
`tests/fixtures/block_kit_constraints.json` (clé renommée
`block_text_limits` → `block_limits`). Même logique qu'en 0007 : pas de
dépendance à un validateur JSON Schema généraliste pour une forme fixe.

## Conséquences

- Le rendu texte (`render`) reste le format des sinks stdout/markdown ;
  sa docstring ne prétend plus régir la mise en page de tous les sinks.
- Un digest sans lignes ni déviations produit un payload réduit au header.
- Post-v0.1 : si un sink Teams (v0.2) arrive, il suivra le même patron —
  blocs natifs du sink, primitives d'affichage partagées de `render`.

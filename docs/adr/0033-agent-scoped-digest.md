# 0033 — Évaluation du digest scopée à l'agent du mandat

**Date** : 2026-08-05 · **Statut** : Accepté · **Signé** : Adrien (arbitrages),
Claude Code (diagnostic et rédaction)

## Contexte

`alfred watch` évaluait **tous** les events du dossier de traces contre le
mandat du projet. Le champ `agent:` du mandat n'était qu'une étiquette
d'affichage : rien ne le confrontait à l'attribut `gen_ai.agent.name` porté par
les traces, alors que le mandat de référence commenté affirme que le champ
« must match ».

Deux agents écrivant dans le même `traces/` produisaient donc, pour chacun, un
digest rapportant des déviations calculées sur les events de l'autre —
`tool_not_allowed` sur des outils parfaitement légitimes pour l'agent qui les a
appelés, budget cumulant les deux, comptes de tâches mélangés. Défaut trouvé au
smoke-test BYOA depuis PyPI le 2026-07-29, suivi en
[#60](https://github.com/adriencr81/Check-Alfred/issues/60), contourné jusqu'ici
par une note « un agent par dossier » dans `docs/integrate.md`.

Le défaut touche directement la règle produit D5 : une déviation ancrée sur un
event ID réel mais imputée au mauvais agent reste une affirmation fausse. C'est
aussi ce qu'un testeur externe rencontre en premier, partager un dossier de
traces étant le cas normal.

## Décisions

**1. L'attribution est une propriété de la trace, pas de l'event.**
`gen_ai.agent.name` n'est porté que par le span de session (`AGENT_TASK`), émis
par `AgentTracer` et par les deux connecteurs natifs ; les spans de modèle et
d'outil sous lui n'en portent pas. Le scoping groupe donc par `trace_id` et lit
le nom sur le span de session.

**2. On exclut ce qu'on peut prouver appartenir à quelqu'un d'autre.** Une trace
nommant un agent *différent* de `mandate.agent` est écartée de l'évaluation :
elle est le sujet de son propre mandat, et la juger ici revient à lui reprocher
des règles qui ne lui ont jamais été données.

**3. On évalue, en le signalant, ce qu'on ne sait pas attribuer.** Une trace ne
nommant aucun agent reste évaluée. L'option inverse — n'évaluer que les traces
portant exactement le nom du mandat, ce que demandait l'énoncé de l'issue — a
été **écartée après relecture du code** : c'est la forme normale d'une trace
arrivant par un pont OTel Collector, et l'exclure viderait en silence le digest
de tous ceux qui n'émettent pas l'attribut. Corriger un bug d'attribution en
introduisant une perte de couverture silencieuse est un plus mauvais échange.

Ces events sont donc remontés à part — `WatchPass.unattributed`, et une notice
stderr pour `alfred watch` comme pour `alfred report` — afin que le doute soit
énoncé plutôt que dissous (principe de l'ADR 0024 : un trou d'audit reste
visible). Deux agents réellement anonymes dans le même dossier restent
indiscernables ; la réponse pour eux est d'émettre `gen_ai.agent.name`, pas de
deviner à leur place.

**4. Le code de sortie ne change pas.** `alfred watch` sort en `1` sur une
quarantaine ou un conflit parce qu'un humain peut réparer le fichier. Un event
non attribuable vient d'un émetteur qui ne pose pas l'attribut : c'est un état
permanent, et un `1` à chaque passage apprendrait à ignorer le signal.

**5. Le scoping vit dans `build_digests`, pas dans `build_digest`.**
`build_digest` documentait déjà son contrat — events pré-scopés à un agent, à la
charge de l'appelant — et n'avait pas tort ; c'est l'appelant qui ne l'honorait
pas. `build_digests` est le seul appelant commun à `alfred watch` et
`alfred report`, donc un seul point de correction couvre les deux commandes.

**6. La baseline glissante est scopée par la même règle.** Second site du même
défaut, non mentionné par l'issue : `_baseline_windows` relisait les jours
antérieurs depuis le store sans aucun filtre. Corriger la seule évaluation
aurait laissé « +180 % vs moy. 7 j » (F3, ADR 0019) comparer le coût du jour à
l'historique d'un autre agent.

## Conséquences

- `src/alfred/watch.py` : `_scope_to_agent` et `unattributed_events` ;
  `build_digests` et `_baseline_windows` scopent ; `WatchPass` gagne
  `unattributed`.
- `src/alfred/cli.py` : notice stderr sur les deux chemins, code de retour
  inchangé.
- `docs/integrate.md` : la section « un agent par dossier » devient « plusieurs
  agents dans un dossier », et décrit la notice.
- Aucun changement du modèle `Digest` ni des rendus. Une ligne de digest
  `UNATTRIBUTED_EVENTS` a été envisagée — elle suivrait le rapport HTML jusqu'au
  manager — puis écartée : elle se répéterait à l'identique dans le digest de
  chaque agent, inscrivant dans le rapport de l'un une affirmation qui ne le
  concerne pas.
- Hors périmètre, à ouvrir séparément : avertir au `alfred mandate lint` quand
  `mandate.agent` ne correspond à aucun agent observé dans les traces.

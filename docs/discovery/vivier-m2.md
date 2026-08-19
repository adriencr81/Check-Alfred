# Vivier M2 — 20 conversations de discovery direct

> Constitué le 2026-08-19 depuis les issues publiques de `langchain-ai/langgraph`
> et `openai/openai-agents-python` (ADR 0034 décision 3, `GROWTH_PLAN_3M.md`
> §2.2). Aucune donnée privée : handles publics et liens d'issues publiques.
> **Statut : aucun contact envoyé à ce jour.**

## Avertissement de lecture, à ne pas sauter

Les trackers de ces deux dépôts sont dominés par des **rapports de bugs
internes à la bibliothèque**, pas par des exploitants qui racontent qu'un agent
a mal agi en production. Le persona visé y est mince : sur ~60 issues balayées,
5 seulement décrivent explicitement un problème de gouvernance ou
d'auditabilité d'agent.

C'est en soi une information, et elle converge avec le bilan M1 : le vocabulaire
d'Alfred (mandat, déviation, preuve ancrée) ne s'exprime presque pas là où on
allait le chercher. Deux lectures possibles — le problème est réel mais se dit
ailleurs (équipes internes, pas trackers open source), ou il n'a pas la
fréquence supposée. **Les 20 conversations servent précisément à trancher entre
les deux**, et ce point doit être testé explicitement, pas contourné.

Conséquence pratique : le tier 1 est court et vaut plus que le reste. Ne pas
diluer l'effort en traitant les 20 lignes comme équivalentes.

---

## Tier 1 — douleur explicite, proche du positionnement d'Alfred

| # | Handle | Source | Ce qu'iel dit | Angle d'entrée |
|---|---|---|---|---|
| 1 | **AAH20** (Ahmed Hassan) | [langgraph#8636](https://github.com/langchain-ai/langgraph/issues/8636) et [#8641](https://github.com/langchain-ai/langgraph/issues/8641) | Propose un `ActionBoundary`/`ActionGate` et un **ledger d'actions hash-chaîné SHA-256** ; cite SOC 2 Type II, ISO 42001, NIST AI RMF. Dans #8641 : des graphes qui « compilent proprement et tournent bien en local, puis donnent des agents bloqués, des nœuds morts silencieux ou des crashes irrécupérables sous trafic réel ». | Le prospect le plus proche du produit, de loin. Il a écrit deux fois la thèse d'Alfred sans le savoir. L'intégrité de preuve d'Alfred (ADR 0026) répond directement à son ledger. **À contacter en premier.** |
| 2 | **Emma Johnson** | [langgraph#8614](https://github.com/langchain-ai/langgraph/issues/8614) | Propose des outils « confirmation-gated » : approbation humaine avant action engageante. | C'est un mandat exprimé en code. Question : comment vérifie-t-iel *après coup* que la gate a tenu ? |
| 3 | **vgudur-dev** | [langgraph#8061](https://github.com/langchain-ai/langgraph/issues/8061) | Validation des checkpoints mémoire contre les attaques par empoisonnement. | Posture sécurité sur l'état de l'agent. Adjacent à la containment de fuite (ADR 0025). |
| 4 | **wilsonhj** (H.J.) | [langgraph#8394](https://github.com/langchain-ai/langgraph/issues/8394) | `ToolNode` avale des interruptions ; parle de « defects d'audit à travers les paquets ». | Quelqu'un qui emploie spontanément le mot *audit* sur un framework d'agents. |
| 5 | **arthi-arumugam-git** | [openai-agents#4434](https://github.com/openai/openai-agents-python/issues/4434) | « Les tokens de compaction sont facturés mais jamais comptés » — l'usage rapporté omet chaque appel `responses.compact`. | Coût réel invisible dans le rapport d'usage. Alfred calcule le coût depuis les events : correspondance directe. |

## Tier 2 — fiabilité en production, angle indirect

| # | Handle | Source | Ce qu'iel dit |
|---|---|---|---|
| 6 | **weike-zhang** | [openai-agents#4515](https://github.com/openai/openai-agents-python/issues/4515) | Une réponse `failed`/`incomplete` est traitée comme un tour vide réussi — **échec silencieux**. Exactement ce que remonte `Surface failed tool calls as their own digest line` (commit `c9b141b`). |
| 7 | **ErenAta16** | [openai-agents#4510](https://github.com/openai/openai-agents-python/issues/4510) | Complétion tronquée à zéro token indiscernable d'un tour vide. Même famille : l'échec ne se voit pas. |
| 8 | **hsusul** | [openai-agents#4070](https://github.com/openai/openai-agents-python/issues/4070), [#4068](https://github.com/openai/openai-agents-python/issues/4068) | Les erreurs de run ne sont jamais attachées au **span** de l'agent ; les résultats de guardrail se perdent. Travaille au niveau span — le substrat d'Alfred. |
| 9 | **dgenio** (Diogo Santos) | [langgraph#7855](https://github.com/langchain-ai/langgraph/issues/7855), [#8032](https://github.com/langchain-ai/langgraph/issues/8032) | « appels de modèle inutiles ; replay/debug plus difficile ; plus de variance entre runs ; frontières d'échec moins nettes ». |
| 10 | **AntonioVFranco** | [langgraph#8115](https://github.com/langchain-ai/langgraph/issues/8115) | « silent data-loss reliability failure under concurrency ». |
| 11 | **White-Mouse** | [langgraph#7988](https://github.com/langchain-ai/langgraph/issues/7988) | `ToolNode` écrase silencieusement les noms d'outils dupliqués avant dispatch. |
| 12 | **tcconnally** | [langgraph#8234](https://github.com/langchain-ai/langgraph/issues/8234), [#8156](https://github.com/langchain-ai/langgraph/issues/8156) | Récupération post-crash qui restaure un état incohérent ; construit ses propres backends de checkpoint. Opère de l'état d'agent réel. |
| 13 | **Free-tek** | [langgraph#7895](https://github.com/langchain-ai/langgraph/issues/7895) | Demande un notebook de patterns **HITL de production**. |
| 14 | **fedegtz** | [langgraph#8613](https://github.com/langchain-ai/langgraph/issues/8613) | Handlers injectés par instrumentation sur le cycle de vie du graphe. Profil instrumentation/OTel. |
| 15 | **GautamSharma99** | [openai-agents#4057](https://github.com/openai/openai-agents-python/issues/4057), [#4053](https://github.com/openai/openai-agents-python/issues/4053) | Deux issues sur le `BatchTraceProcessor` et l'export de traces. Connaît la plomberie de tracing. |
| 16 | **zhuziqi97** | [openai-agents#4270](https://github.com/openai/openai-agents-python/issues/4270) | Veut préserver les données d'usage brutes dans la réponse modèle — traçabilité du coût. |
| 17 | **russeell** | [openai-agents#4393](https://github.com/openai/openai-agents-python/issues/4393) | Le handler `max_turns` contourne la sémantique des guardrails de sortie. |
| 18 | **LHMQ878** | [openai-agents#4125](https://github.com/openai/openai-agents-python/issues/4125) | Un guardrail déclenché laisse un appel d'outil orphelin en reprise streamée. |
| 19 | **ozguraslanCE** | [langgraph#8408](https://github.com/langchain-ai/langgraph/issues/8408) | Les détails de trace échouent en 404 dans Studio. Utilise activement une UI de traces. |
| 20 | **SashaMIT** | [langgraph#8522](https://github.com/langchain-ai/langgraph/issues/8522) | Suit une CVE de sérialisation et son défaut de configuration en production. Posture sécurité/prod. |

## Contacts chauds — hors issues, à traiter en premier avec le tier 1

Ces deux personnes ont **déjà contribué à Alfred** sans qu'aucun canal ne soit
ouvert. Ce sont les seuls contacts du vivier qui connaissent déjà le produit.

| Handle | Lien | Contexte |
|---|---|---|
| **KIRA-L001** | [Check-Alfred#53](https://github.com/adriencr81/Check-Alfred/pull/53) | A ajouté le pricing DeepSeek à la table de coûts (issue #50). |
| **sahilsaiyed-oss** | [Check-Alfred#54](https://github.com/adriencr81/Check-Alfred/pull/54) | A ajouté le mandat d'exemple `support-triage-bot` (issue #51). |

## Cas à part — piste entreprise, pas utilisateur

**atensecurity-bot** — [langgraph#8102](https://github.com/langchain-ai/langgraph/issues/8102),
« Pre-execution tool call interception hooks for policy enforcement ». C'est le
compte automatisé d'un éditeur de sécurité, pas un exploitant : à lire comme un
signal de marché (quelqu'un finance ce problème) et éventuellement un
concurrent, **pas** comme une des 20 conversations.

---

## Le message d'ouverture

Une question, pas un pitch. Aucun lien vers Alfred dans le premier message —
la règle vaut aussi quand la tentation est forte parce que la personne semble
parfaitement ciblée.

> Salut — j'ai lu ton issue sur *[sujet précis, en une demi-phrase qui prouve
> qu'on l'a lue]*. Je creuse une question voisine en ce moment : **quand un
> agent fait une erreur en production, comment tu l'apprends aujourd'hui ?**
> Par un utilisateur qui remonte le problème, par une alerte, en relisant des
> traces ? Je ne vends rien, j'essaie de comprendre si le problème est réel ou
> si je me le raconte. 15 minutes si tu as le temps, ou juste une réponse
> écrite si tu préfères.

Trois règles tenues sans exception :

1. **Personnaliser la première demi-phrase** avec le contenu réel de leur issue.
   Un message générique se repère en une seconde et brûle le contact.
2. **Ne pas défendre Alfred** si la réponse est « ça ne nous arrive pas ». C'est
   la réponse la plus précieuse du lot — elle falsifie la thèse, ce qui est le
   but.
3. **Noter la réponse le jour même** dans le journal ci-dessous, verbatim et
   sans interprétation.

## Journal des échanges

Une ligne par contact, ajoutée au fil de l'eau. Un discovery non écrit n'a
jamais eu lieu.

| Date | Handle | Canal | Réponse (verbatim, brut) | Décrit une douleur réelle ? |
|---|---|---|---|---|
| — | — | — | *aucun contact envoyé* | — |

**Critère de succès, fixé d'avance (ADR 0034 décision 3)** : ≥ 10 des 20
décrivent un processus réel et douloureux → la thèse tient, le M3 repart sur la
distribution. Sinon → le problème n'a pas la fréquence supposée, et c'est cette
conclusion qu'il faut acter.

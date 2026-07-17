# 0006 — Conception de la NLG vérifiée (Brique 4)

**Date** : 2026-07-17 · **Statut** : Accepté · **Signé** : Claude Code (Brique 4)

## Contexte

Le PLAN.md (§5, Brique 4) fixe le test-clé (`test_narrated_digest_only_uses_
source_events`, « le test qui incarne la thèse du produit ») et la DoD (LLM
configurable OpenAI-compatible, stub en test, doc `docs/verified_nlg.md`),
mais laisse ouverts : la structure de fichiers (l'esquisse §4 ne liste que
`narrate/{__init__.py, llm.py}`), la forme exacte de `NarratedDigest`/
`Sentence`, le scope de la narration (`Digest.lines` seulement, ou aussi les
`Deviation` ?), la conception du client HTTP, et la granularité
d'application de la garantie. Deux points ont été tranchés avec l'utilisateur
avant implémentation, suivant la même discipline que les ADR 0004/0005.

## Décisions

**1. Scope — lignes uniquement, pas les déviations.** Décision utilisateur
explicite, confirmée avant implémentation. Les `Deviation` portent déjà un
`.message` déterministe et anchré (`alfred.mandate.model.Deviation`,
généré par du code, pas par un LLM) — aucun risque d'hallucination à couvrir,
donc aucune narration LLM nécessaire. `narrate()` n'itère que sur
`digest.lines`.

**2. Structure de fichiers — ajout de `narrate/model.py`, déviation
documentée de PLAN.md §4.** L'esquisse `narrate/{__init__.py, llm.py}` est un
plan de fichiers de haut niveau, pas un invariant verrouillé (contrairement
aux contrats de PLAN.md §3). `mandate/` et `report/` séparent déjà
systématiquement les types purs (`model.py`) de la logique
(`engine.py`/`build.py`). On suit cette convention établie :
`narrate/model.py` porte `NarratedDigest` et `Sentence` (types purs, sans
import de `llm.py`), `narrate/llm.py` porte toute la logique d'application de
la garantie et le client HTTP. Contrairement à `Line`/`Deviation`,
`Sentence`/`NarratedDigest` n'ont pas de `__post_init__` de validation — la
garantie de citation est appliquée activement par `narrate()`, pas
passivement par le dataclass, précisément pour que `model.py` reste sans
dépendance sur la logique d'extraction de citations.

**3. Format de citation — réutilisation exacte de `[evt:id1, id2]`.** Même
convention bracket que `alfred.report.render._format_sources`, extraite par
`extract_event_ids` (regex `\[evt:([^\]]*)\]`). Un seul format de citation
dans tout le codebase, un seul point de vérité pour son extraction.

**4. Granularité d'application — échec total du call à la première
violation, pas de dégradation ligne par ligne.** `narrate()` appelle le LLM
une fois par `Line` de `digest.lines` (ordre préservé) ; à la première
`Sentence` dont les citations sont vides ou hors `line.sources`,
`NarrateError` est levée immédiatement et aucun `NarratedDigest` partiel
n'est retourné. Cohérent avec la règle produit ABSOLUE (CLAUDE.md) : « STOP,
replanifier » plutôt que « ignorer silencieusement la ligne fautive ».

**5. Un appel LLM par ligne, jamais tout le digest d'un coup.** Chaque appel
porte sur une seule `Line` et ses `sources`, pas sur le digest entier. Cela
rend la frontière de citation que le LLM doit respecter toujours identique à
exactement une liste de `sources` — plus simple à prompter, plus simple à
vérifier, et un `NarrateError` pointe sans ambiguïté vers la ligne fautive.

**6. Client LLM — vrai client HTTP minimal maintenant, pas seulement le
Protocol.** Décision utilisateur explicite, confirmée avant implémentation.
`LLMClient` est un `Protocol` (`complete(prompt: str) -> str`) ; en plus du
stub de test, `OpenAICompatibleClient` (dataclass gelé) parle le format
standard `POST {base_url}/chat/completions` (payload
`{"model", "messages": [{"role": "user", "content": prompt}]}`, réponse
`choices[0].message.content`) via `urllib.request` de la stdlib uniquement —
zéro nouvelle dépendance (cf. CLAUDE.md « Pas de dépendance lourde sans
justification écrite »). Aucun retry/backoff/streaming en v0.1 (YAGNI) : un
endpoint défaillant remonte en `NarrateError`, cohérent avec le principe
« fail loudly ».

**7. `Transport` à un seul paramètre positionnel.** Le point d'injection HTTP
de `OpenAICompatibleClient` est un `Transport` (`Protocol` avec
`__call__(self, request: HTTPRequest) -> bytes`) plutôt que des paramètres
nommés multiples. Un unique paramètre positionnel évite un piège mypy
--strict : le matching structurel d'un `Protocol.__call__` à paramètres
nommés exige que l'implémentation concrète (ou le fake de test) utilise
exactement les mêmes noms de paramètres, ce qui est fragile pour des fakes de
test écrits indépendamment. `_urllib_transport` (implémentation par défaut,
appelle réellement `urllib.request.urlopen`) est assigné directement comme
valeur par défaut du champ `transport` du dataclass gelé — aucun appel réseau
réel dans la suite de tests, qui injecte systématiquement un fake.

## Conséquences

- `alfred.narrate` ne dépend d'aucun autre module de Brique 4+ ; il consomme
  `alfred.report.model.{Digest, Line}` et `alfred.trace.model.EventId`
  uniquement. Aucun câblage CLI (`alfred.cli`) — prévu Brique 5.
- `pyproject.toml` inchangé : `urllib.request`, `json`, `re` (stdlib) suffisent.
- Tests falsifiables : `tests/test_narrate_llm.py` — le test littéral de
  PLAN.md, les cas de rejet (citation manquante, hallucinée, partiellement
  hallucinée), la préservation de l'ordre des lignes, l'échec total du call,
  et la construction/parsing de requête HTTP du client OpenAI-compatible via
  un transport fake (aucun réseau réel).
- Un appelant qui veut un digest même quand la narration échoue doit
  `except NarrateError` et retomber sur `alfred.report.render.render(digest)`
  — documenté dans `docs/verified_nlg.md`, pas encodé dans `narrate()`
  lui-même (pas de fallback silencieux intégré, cohérent avec « fail
  loudly »).

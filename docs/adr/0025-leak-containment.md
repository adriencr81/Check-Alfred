# 0025 — Confinement des fuites : PII au repos, credentials en transit

**Date** : 2026-07-25 · **Statut** : Accepté · **Signé** : Adrien (« lot 3 »),
Claude Code (pentest + conception)

## Contexte

Lot 3 du pentest du 2026-07-25. Les ADR 0023 (mandat contournable) et 0024
(auditeur arrêtable) portaient sur la *justesse* et la *disponibilité* du
contrôle. Ici, il s'agit de ce qu'Alfred **laisse fuir** de ce qu'on lui
confie : les données clients de ses utilisateurs et leurs credentials. C'est
le blocage dur pour les secteurs régulés visés par PLAN.md §7.

1. **La redaction PII est contournée par le blob JSON brut.**
   `trace/ingest.py::_flatten_tool_arguments` copie les arguments scalaires de
   `gen_ai.tool.call.arguments` vers `tool.arguments.<clé>`, mais **laisse le
   blob d'origine** dans les attributs ; `trace/redact.py::_is_redacted` ne
   reconnaît que la clé exacte ou `tool.arguments.<nom>`. PoC : un mandat
   déclarant `redact: [customer_email]` masque bien
   `tool.arguments.customer_email`, pendant que
   `gen_ai.tool.call.arguments` conserve `{"customer_email":
   "alice@example.com"}` — **en clair dans SQLite**. C'est la contradiction
   directe de l'ADR 0022 (« the raw value never lands in SQLite »), et elle
   s'applique à la voie d'ingestion la plus standard (semconv OTel), pas à un
   cas tordu.
2. **La clé API LLM fuit sur redirection, et le clair est accepté.** `urllib`
   conserve les en-têtes personnalisés à travers une redirection, y compris
   vers un autre hôte : PoC, un endpoint qui répond `302` fait livrer
   `Authorization: Bearer sk-SECRET-KEY` à l'hôte de son choix. Et
   `llm_base_url` n'est validé **nulle part** (ni à `init`, ni au chargement),
   donc `http://` envoie la même clé en clair sur le réseau.
3. **Le webhook Slack est traité comme de la configuration, pas comme un
   secret.** Son chemin *est* le credential. Il est écrit en `0644` dans
   `.alfred/config.toml` (lisible par tout utilisateur local, alors que la clé
   LLM, elle, reste en variable d'environnement) ; son hôte n'est pas vérifié
   (`https://attacker.example/collect` est accepté sans un mot) ; son schéma
   n'est revalidé nulle part après `init`, donc un `http://` écrit à la main
   part en clair ; et le message d'erreur du garde de schéma imprime l'URL
   complète, donc le secret, dans les logs. Même sujet : `trace.db` et
   `.alfred/seen.json` contiennent des arguments d'outils et sont eux aussi en
   `0644`.

## Décisions

**1. La redaction descend dans le blob d'arguments.** Quand la clé est
`gen_ai.tool.call.arguments`, la valeur est parsée et chaque clé nommée dans
`redact` est masquée **récursivement** (objets et listes imbriqués), puis
re-sérialisée. Alternative écartée : supprimer le blob après aplatissement —
l'aplatissement ne copie que les scalaires, on perdrait les arguments
structurés que le blob est seul à porter.

**2. Un blob illisible avec une liste `redact` non vide est masqué en entier.**
Fail-closed : si on ne peut pas inspecter le contenu, on ne peut pas garantir
qu'il ne porte pas la PII nommée. Le déployeur a demandé le masquage ; on ne le
lui refuse pas au motif que le JSON est cassé.

**3. Le masque devient un HMAC-SHA256 à clé par projet.** `redacted:hmac:<12
hex>` remplace `redacted:sha256:<12 hex>`. La clé (32 octets `os.urandom`) est
créée à la première redaction dans `.alfred/redaction-key` en `0600`, et n'est
créée **que** si `redact` est non vide. Ceci **révise l'ADR 0022** : sa
décision 3 (hash non salé) et la limite « hash devinable par force brute »
tombent. L'égalité entre valeurs identiques est préservée à l'intérieur d'un
projet, donc `loop_detected` et la détection de répétition continuent de
fonctionner sur un champ masqué — c'était la raison d'être du choix initial, et
elle est satisfaite sans laisser un email se retrouver par dictionnaire.
Conséquence assumée : les jetons ne sont plus comparables entre projets ou
machines, et perdre la clé change tous les jetons *futurs* (les anciens, déjà
stockés, restent tels quels).

**4. HTTPS obligatoire, sauf loopback.** Toute requête sortante passe par une
règle unique : `https://`, ou `http://` vers `127.0.0.1` / `::1` / `localhost`.
L'exception loopback existe pour le cas réel du modèle auto-hébergé (ollama,
llama.cpp, vLLM), où le trafic ne quitte pas la machine. Appliquée à `init` et
au chargement de la config, plus au moment de la requête.

**5. Une redirection qui change d'hôte est refusée.** Un opener dédié refuse
tout `3xx` vers un autre hôte plutôt que d'y renvoyer les en-têtes. C'est la
faille exacte du PoC ; la suivre en dépouillant l'`Authorization` serait déjà
mieux, mais aucun endpoint LLM ou webhook légitime n'a besoin d'un rebond
cross-host sur un POST.

**6. Les messages d'erreur ne citent plus qu'un `scheme://host`.** Le chemin
d'un webhook Slack est son mot de passe ; il n'a rien à faire dans un log ou
une trace d'erreur.

**7. Les fichiers du projet sont créés en `0600`.** `config.toml`,
`trace.db`, `.alfred/seen.json` et la clé de redaction, via un helper partagé
`alfred/_fs.py`. Et `ALFRED_SLACK_WEBHOOK_URL` (env, prioritaire sur le
fichier) permet de ne jamais écrire le webhook sur disque — la même discipline
que `ALFRED_LLM_API_KEY` depuis l'ADR 0007.

**8. Un hôte de webhook non-Slack est averti, pas refusé.** HTTPS reste une
erreur dure ; un hôte autre que `hooks.slack.com` déclenche un avertissement à
`init` et au chargement. Refuser casserait les endpoints compatibles
(Mattermost, proxys internes) qui sont un usage légitime ; se taire laisserait
une exfiltration configurée passer inaperçue.

## Règle produit (D5) — non violée

Aucune affirmation n'est fabriquée ni retirée : on masque des valeurs et on
refuse des destinations. Chaque ligne reste ancrée sur ses `event_id`, et le
masque préserve l'égalité dont dépendent les contrôles.

## Limites assumées

- **Aveugle hors liste.** Seuls les champs déclarés dans `redact` sont masqués
  (ADR 0022, décision 2, inchangée) : une PII dans un attribut non listé passe.
- **Pas d'allowlist SSRF.** `llm_base_url` et `slack_webhook_url` viennent de
  l'opérateur, pas d'une entrée non fiable : restreindre les plages privées
  casserait les déploiements internes sans fermer de vecteur réel.
- **`chmod` n'a pas la même portée partout.** Sous Windows, `0600` est
  approximatif ; la protection réelle y dépend des ACL NTFS.
- **Le nom du span n'est pas masqué.** `tool_call.<outil>` et `agent.task`
  peuvent porter un identifiant métier ; ce sont des noms, pas des attributs,
  donc hors du vocabulaire déclaratif de `redact`.
- **Perte de clé.** Remplacer `.alfred/redaction-key` ne casse rien mais rend
  les jetons futurs incomparables aux anciens : une détection de boucle à
  cheval sur la rotation peut manquer une répétition.

## Conséquences

- `src/alfred/trace/redact.py` : `Redactor`, HMAC, descente dans le blob.
- `src/alfred/trace/ingest.py` : paramètre `Redactor | None`.
- `src/alfred/_http.py` : règle de schéma, opener anti-redirection, messages
  masqués.
- `src/alfred/config.py` : validation à `init` et au chargement, env var
  webhook, avertissement d'hôte.
- Nouveau `src/alfred/_fs.py` : écritures en `0600` (réutilisé par `config.py`,
  `watch.py`, `trace/store.py`).
- Tests falsifiables : `tests/test_trace_redact.py`, `tests/test_http.py`,
  `tests/test_config.py`, `tests/test_watch.py`.
- Docs : CHANGELOG, `docs/integrate.md`, note de révision dans l'ADR 0022.
- DoD inchangée : `pytest -q`, `ruff check .`, `mypy --strict src/` verts.

# Manuel de test Alfred — brancher Alfred sur vos agents

> À l'attention des devs qui testent Alfred sur leurs propres agents IA.
> Objectif : en ~15 min, faire produire à Alfred un **digest quotidien**
> où **chaque ligne est ancrée à un événement de trace réel** (`[evt:…]`).
> Aucune ligne n'est auto-déclarée par l'agent ni inventée par un LLM.

**Dépôt GitHub :** https://github.com/adriencr81/check-alfred

---

## 0. Ce que fait Alfred (en une phrase)

Alfred lit les **traces** de vos agents (une trace = un fichier par run),
les confronte à un **mandat** que vous déclarez en YAML (outils autorisés,
budget, actions interdites, seuils d'escalade), et produit un **digest**
quotidien listant l'activité et les **déviations** — chacune prouvée par
l'ID de l'événement qui la déclenche.

Trois notions à retenir :

| Terme | Sens |
|---|---|
| **mandate** | le YAML déclaratif : ce que l'agent *a le droit* de faire |
| **trace event** | un span OpenTelemetry normalisé (tâche, appel modèle, appel outil) |
| **deviation** | une contradiction typée entre la trace et le mandat |

---

## 1. Installation (2 min)

Prérequis : **Python 3.11+**. Alfred n'est pas encore sur PyPI, on installe
depuis le clone.

```bash
git clone https://github.com/adriencr81/check-alfred.git
cd check-alfred
pip install -e ".[dev]"
```

Vérifiez que tout tourne, sans aucune config, sans clé API, sans réseau :

```bash
alfred demo
```

Vous devez voir un digest s'afficher en stdout (un faux agent instrumenté →
vraie trace → vrai digest). Si ça marche, votre install est bonne.

> Astuce : `alfred --help` liste toutes les commandes ; `alfred <cmd> --help`
> détaille chacune.

---

## 2. Le tour de chauffe : l'exemple à 5 minutes (aucune clé API)

Avant de brancher votre agent, faites tourner l'exemple minimal fourni. Il
prouve la boucle complète (instrumenter → surveiller → digest ancré) avec un
agent jouet de ~30 lignes, sans LLM ni réseau.

```bash
# 1) L'agent tourne et écrit sa trace
python examples/agents/minimal/agent.py        # → traces/expense-bot-<ts>.json

# 2) On scaffolde un projet Alfred et on y pose le mandat de l'exemple
alfred init demo --agent expense-bot
cp examples/agents/minimal/mandate.yaml demo/mandate.yaml

# 3) Alfred lit la trace et sort le digest
alfred watch traces/ --project demo
```

Résultat attendu (les IDs seront ceux de *votre* run) :

```
Alfred · expense-bot · <aujourd'hui>

Tasks completed:           3   [evt:…]
Deviations (mandate):      1   [evt:…] — forbidden_action: approve_expense called with amount_eur=250.0 > 100.0
```

Alfred a attrapé la 3ᵉ demande (250 €, au-dessus du plafond de 100 € déclaré
dans le mandat). Rien n'est scripté : le digest ne dit que ce que la trace
prouve.

---

## 3. Brancher VOTRE agent

Alfred vérifie un run seulement si ce run **laisse une trace qu'il sait lire**.
Choisissez le chemin qui correspond à votre agent — les 3 marchent aujourd'hui.

### Chemin A — SDK `alfred.instrument` (n'importe quelle boucle, ~10 lignes)

Le plus universel. Vous entourez votre boucle, vos appels modèle et vos appels
outil avec des context managers. Stdlib uniquement, pas besoin du SDK OTel.

```python
from alfred.instrument import AgentTracer

tracer = AgentTracer(agent="support-bot", traces_dir="traces/")

with tracer.session(task_name="handle_ticket", task_id="TCK-42"):
    with tracer.llm_call(model="claude-opus-4-8") as llm:
        response = client.messages.create(...)      # votre appel existant
        llm.record_usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
    with tracer.tool_call("send_email", arguments={"to": "x@example.com"}) as tool:
        result = send_email(...)                     # votre outil existant
        tool.record_result(status="ok")

tracer.flush()   # → traces/support-bot-<timestamp>.json
```

Ce qu'il faut savoir :

- **`session()`** = une tâche de l'agent. Le span est émis à la sortie du
  bloc, même en cas de crash.
- **`llm_call()`** = un appel modèle. Si vous ne connaissez le modèle qu'après
  coup, omettez `model=` et passez `record_usage(..., response_model=response.model)`.
  Le coût est calculé depuis les tokens (table de prix `alfred.trace.cost`) ;
  passez `cost_eur=` si vous le calculez vous-même (il l'emporte toujours).
- **`tool_call(name, arguments={...})`** = un appel outil. Les arguments
  scalaires deviennent des attributs `tool.arguments.<clé>` — c'est **exactement
  ce que lisent les règles du mandat** (ex. `issue_refund_above_100_eur` lit
  `amount_eur`). Une sortie propre sans `record_result` enregistre `status="ok"` ;
  une exception enregistre `"error"` et se propage.
- **`flush()`** = écrit tout ce qui a été enregistré dans un fichier et
  renvoie son chemin. Appelez-le une fois, à la fin.

Exemple complet et exécutable (vraie boucle Claude instrumentée) :
`examples/agents/refund_bot/`.

### Chemin B — Connecteur LangGraph (zéro instrumentation manuelle)

```bash
pip install alfred-ai[langgraph]
```

```python
from alfred.instrument import AgentTracer
from alfred.integrations.langgraph import AlfredCallbackHandler

tracer = AgentTracer(agent="support-bot", traces_dir="traces/")
graph.invoke(inputs, config={"callbacks": [AlfredCallbackHandler(tracer)]})
tracer.flush()
```

Chaque appel modèle / outil du graphe devient un span, même forme et même
garantie qu'au chemin A. Le handler ne lève jamais dans votre graphe.
Exemple : `examples/agents/langgraph_bot/`.

### Chemin C — Connecteur OpenAI Agents SDK (zéro instrumentation manuelle)

```bash
pip install alfred-ai[openai-agents]
```

```python
from agents import Agent, Runner, set_trace_processors
from alfred.instrument import AgentTracer
from alfred.integrations.openai_agents import AlfredTracingProcessor

tracer = AgentTracer(agent="support-bot", traces_dir="traces/")
set_trace_processors([AlfredTracingProcessor(tracer)])   # Alfred seul, hors-ligne
Runner.run_sync(agent, "handle the ticket")
tracer.flush()
```

`set_trace_processors` rend Alfred exclusif (rien n'est envoyé au backend
OpenAI). Utilisez `add_trace_processor(...)` pour garder aussi l'export du SDK.
Exemple : `examples/agents/openai_agents_bot/`.

### (Bonus) Déjà instrumenté OpenTelemetry ?

Si vos agents émettent déjà des spans GenAI OTel, pas besoin du SDK Alfred :
pointez un OTel Collector avec son *file exporter* vers le dossier surveillé.
Il faut que vos spans d'outil portent `gen_ai.operation.name: execute_tool` et
`gen_ai.tool.name`. Config détaillée : `docs/integrate.md` § *OTel Collector bridge*.

---

## 4. Déclarer le mandat (le YAML)

Créez un `mandate.yaml`. C'est le contrat que vous voulez faire respecter.

```yaml
# mandate.yaml
agent: support-bot            # DOIT matcher gen_ai.agent.name porté par la trace
allowed_tools: [send_email, read_ticket]
daily_budget_eur: 5.0
forbidden_actions:
  - send_marketing              # nom d'outil exact
  - issue_refund_above_100_eur  # motif <outil>_above_<montant>_eur
escalate_when:
  - tool_error_rate > 0.10
  - budget_used > 0.80
```

### Ne pas partir de zéro : seeder depuis les traces

Écrire le premier mandat est la marche la plus haute. Laissez Alfred proposer
ce qu'il a **observé** dans vos traces (outils réellement appelés, budget
constaté) :

```bash
alfred mandate init --from-traces traces/ > mandate.yaml
```

> ⚠️ Ce qui est proposé, c'est ce que l'agent **A fait**, pas ce qu'il **A le
> droit** de faire. Ajoutez de la marge au budget, et remplissez vous-même
> `forbidden_actions` / `escalate_when` — la politique se déclare, elle ne
> s'infère pas d'une trace.

### Valider avant de s'en servir

```bash
alfred mandate lint mandate.yaml
```

Sort en **exit 1** sur erreur (un `escalate_when` mal typé, par ex.) — idéal en
CI ou pre-commit avant qu'un run `watch` ne casse dessus.

### Les déviations qu'Alfred sait détecter

| Type | Déclenché quand… |
|---|---|
| `tool_not_allowed` | un outil hors `allowed_tools` est appelé |
| `forbidden_action` | un appel matche une règle `forbidden_actions` (nom exact ou seuil `<outil>_above_<montant>_eur`) |
| `budget_exceeded` | le coût du jour (tokens → €) dépasse `daily_budget_eur` |
| `escalation_missed` | un seuil `escalate_when` est franchi mais l'agent n'a jamais escaladé |
| `required_action_missing` | une obligation déclenchée reste non tenue (ex. remboursement émis sans notification client) |
| `loop_detected` | le même outil appelé ≥ `loop_threshold` fois de suite avec les mêmes arguments (défaut 3) |

Mandat de référence commenté : `examples/mandates/refund-bot.yaml`.

---

## 5. Lancer Alfred sur vos traces

Scaffoldez un projet une fois, posez-y le mandat, puis surveillez :

```bash
alfred init my-project --agent support-bot
cp mandate.yaml my-project/mandate.yaml
alfred watch traces/ --project my-project
```

`alfred watch` fait **une passe et s'arrête** (par choix : pas de démon, pas
d'infra). Seuls les fichiers de trace nouveaux produisent un digest.

### Le rendre quotidien

Deux options :

```bash
# Cron (recommandé) — alfred écrit la ligne de crontab pour vous
alfred schedule traces/ --project my-project --at 09:00 >> mycrontab
crontab mycrontab

# Boucle (conteneurs / CI sans cron) — re-scanne toutes les --interval secondes
alfred watch traces/ --project my-project --loop --interval 300
```

### Alertes temps réel (optionnel, nécessite Slack)

Une déviation à 250 € ne devrait pas attendre le digest du lendemain. Avec un
webhook Slack configuré, chaque passe qui attrape une déviation pousse une
alerte immédiate ancrée sur les IDs fautifs :

```bash
# Le webhook s'écrit dans .alfred/config.toml
alfred init my-project --agent support-bot \
  --slack-webhook https://hooks.slack.com/services/T0/B0/xyz

alfred watch traces/ --project my-project --loop --interval 60 --alerts
```

Sans webhook, `--alerts` avertit et ne fait rien (les déviations restent dans
le digest).

---

## 6. Sorties du digest

- **stdout** (toujours) — la table calculée brute.
- **Slack** (si webhook configuré) — le digest en Block Kit.
- **HTML partageable** — un fichier autonome par jour (styles inline, zéro JS,
  zéro réseau), que chaque manager peut transférer ; chaque ligne pointe vers
  ses IDs d'événements source :

  ```bash
  alfred report traces/ --project my-project --html --out reports/
  ```

- **Prose vérifiée** (optionnel) — `--narrate` réécrit le digest en phrases
  courtes par un LLM. Le LLM **ne fait que reformuler** : chaque citation
  `[evt:…]` est vérifiée contre les événements source, et une citation
  hallucinée **fait échouer le run** au lieu d'être livrée. Nécessite un
  endpoint OpenAI-compatible :

  ```bash
  alfred init my-project --agent support-bot \
    --llm-base-url https://api.openai.com/v1 --llm-model gpt-4o-mini
  export ALFRED_LLM_API_KEY=sk-…          # la clé reste dans l'env, jamais sur disque
  alfred watch traces/ --project my-project --narrate
  ```

  Sans endpoint résolvable, `--narrate` échoue en exit 1 — jamais de repli
  silencieux. `alfred demo` reste sans LLM.

---

## 7. Checklist de test à nous remonter

Merci de tester dans cet ordre et de noter ce qui coince :

- [ ] `alfred demo` produit bien un digest
- [ ] L'exemple minimal (§2) attrape la déviation à 250 €
- [ ] Mon agent écrit une trace (`traces/<agent>-<ts>.json` non vide) via le
      chemin A, B ou C
- [ ] `alfred mandate init --from-traces` propose des `allowed_tools` cohérents
- [ ] `alfred mandate lint` passe (exit 0)
- [ ] `alfred watch` sort un digest où le nombre de tâches correspond à mes runs
- [ ] Une déviation volontaire (outil interdit, dépassement de budget) est bien
      détectée **et ancrée** à un `[evt:…]`
- [ ] (si applicable) Le digest Slack / HTML arrive correctement

### Ce qu'on veut savoir

1. **Le branchement** : quel chemin (A/B/C), combien de lignes, ce qui a été
   ambigu.
2. **Le mandat** : ce que `mandate init` a raté ou mal deviné.
3. **Les déviations** : faux positifs, faux négatifs, ou une déviation non
   ancrée (ce serait un **bug**, la règle produit dit que toute ligne DOIT être
   ancrée à un événement).
4. **Frictions** : messages d'erreur peu clairs, doc manquante.

---

## 8. Dépannage rapide

| Symptôme | Cause probable / fix |
|---|---|
| `no new trace files` | le dossier `traces/` est vide, ou tous les fichiers ont déjà été vus (relancez avec de nouvelles traces) |
| `no trace events found … (expected *.json)` | mauvais dossier, ou `flush()` non appelé |
| L'agent du digest ne matche pas mon mandat | `agent:` dans le YAML doit être **identique** à `gen_ai.agent.name` porté par la trace (l'`agent=` passé à `AgentTracer`) |
| Une règle `forbidden_actions` ne se déclenche pas | l'argument testé doit être un scalaire passé dans `arguments={...}` → devient `tool.arguments.<clé>` |
| `--narrate` sort en erreur | endpoint LLM ou `ALFRED_LLM_API_KEY` manquant (c'est voulu : pas de repli silencieux) |
| `--alerts` ne pousse rien | aucun webhook Slack configuré (`alfred init --slack-webhook …`) |

Doc d'intégration complète : `docs/integrate.md`.
Une remarque, un doute sur le mandat ou le seuil de déviation ? Demandez —
mieux vaut poser la question que deviner.
```
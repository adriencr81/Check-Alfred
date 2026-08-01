# How do you verify what your AI agent actually did?

Short answer: you don't verify "what your agent did." You verify one claim at a
time, at one level of proof, and the level worth paying for depends on what
breaks if the agent is wrong.

That sounds evasive. It's the opposite — it's the only precise answer, and it
explains why the advice on this topic is such a mess. "Verify the agent" bundles
six different questions into one phrase, and every tool on the market answers
one of them while its landing page implies all six. A signed receipt proves an
API call happened; it cannot tell you whether the call was allowed. An
observability dashboard shows you the execution path; it cannot tell you whether
the work should count.

My day job is verification and qualification of critical systems — cyber and
space. In that world, nothing ships on someone's word. Every requirement has a
test, every test has a pass criterion, every result leaves evidence, and a claim
with nothing behind it has an official name: a non-conformity. Then I watched
how we deploy AI agents, and we grant them the one thing no critical system ever
gets — they write their own report certifying that they did their job, and we
file it.

So here is the ladder I actually use. Six levels, each defined by the question
it answers. Then two things that keep getting ranked as levels and aren't.

*Disclosure before anything else: I maintain an open-source tool in this space.
It lives at levels 1 to 3, and I'll tell you exactly where it stops.*

---

## V0 — Self-report

**Question:** what does the agent say it did?

```json
{ "status": "success", "message": "Invoice sent." }
```

**Proves:** nothing.

Not "little." Nothing. The same model, in the same context, produced both the
work and the verdict on the work. The self-evaluation literature has measured
this bias directly: models rate their own output above other models' output,
systematically. Asking an agent whether it succeeded is putting the defendant
on the stand as the only witness — and skipping cross-examination.

**When it's enough:** when the agent's actions touch nothing real. For an agent
with tools, that describes no agent worth deploying.

---

## V1 — Execution trace

**Question:** what sequence of calls actually ran?

Structured spans: which tool, which arguments, at what time, returning what,
erroring or not. OpenTelemetry's GenAI semantic conventions give you a standard
for it, but any structured log with a correlation ID qualifies.

**Proves:** that a call was made, with these arguments, and how it terminated.

**Doesn't prove:** that the call was permitted. Or that it changed anything.

**Cost:** near zero if you already emit traces.

And V1 already catches a failure most teams never look for: **the agent
declaring victory over a tool call that errored.** The error status is sitting
right there in the span. If your report doesn't surface it, you don't have a
detection problem — you have a reporting problem, and the evidence was in your
store the whole time.

---

## V2 — Evidence

**Question:** do I hold an artifact I could hand to someone who doubts me?

A Message-ID. A SHA-256 of the delivered file. The ID of the record that was
created. A signed request/response pair. An append-only log entry.

**Proves:** that a specific, independently checkable artifact is bound to the
action.

**Doesn't prove:** that the intended effect exists in the target system. A
receipt is transport-layer proof, and the vendors selling receipt layers say so
in their own docs — it just tends to fall off the slide by the time it reaches a
procurement deck.

**When it's enough:** disputes, reconstruction, non-repudiation.

---

## V3 — Authorization

**Question:** was this action allowed in the first place?

This level needs an input that no run can generate: a specification written
*before* execution, stating what the agent may do. Allowed tools. Thresholds.
Obligations that follow from certain actions. A budget. Conditions under which
it must escalate. Then you hold the observed trace against it, line by line.

**Proves:** that each observed action conforms — or doesn't — to a declared
mandate.

**Doesn't prove:** that the action had its effect.

**Cost:** low. The hard part is writing the specification down, not checking it.

This is the level the market names most and ships least. It travels under many
aliases — "task contract," "policy," "acceptance criteria," "definition of
done" — and almost nobody hands you a file format for it. Yet without it, the
levels below are inert. A flawless execution trace of an action nobody
authorized is not an audit trail. It's a well-documented incident.

In qualification terms: evidence of execution is worthless without a requirement
to hold it against. That isn't philosophy. It's the entire reason the V-model
has a left-hand side.

```yaml
agent: refund-bot-v3

allowed_tools: [read_order, issue_refund, notify_customer, escalate_to_human]
daily_budget_eur: 5.00

forbidden_actions:
  - issue_refund_above_100_eur
  - send_marketing

escalate_when:
  - tool_error_rate > 0.10
  - budget_used > 0.80
escalation_tools:
  - escalate_to_human

required_actions:
  - when_tool: issue_refund
    require_tool: notify_customer
```

---

## V4 — Independent outcome verification

**Question:** did the intended change actually land?

Don't ask the agent. Go look. Query the database. Search the Sent folder. Hit
the API and confirm the record exists. And do it **through a different path than
the one the action took** — if the write and the check share a client, they
share failure modes, and your check inherits the very blindness it was built to
remove.

**Proves:** that the system of record carries the result.

**Doesn't prove:** that it was the right thing to do.

**Cost:** high. One verifier per action type, each one maintained forever.

This is the only level that closes the gap between "the call returned 200" and
"the effect exists." No trace can close it — a trace records that a request went
out and a response came back, not that the row landed. If your agent moves
money, contacts customers, or does anything you can't take back, V4 is not a
nice-to-have.

---

## V5 — Preserved invariants

**Question:** is everything that should have stayed true still true?

Almost nobody implements this level, and it's the one aimed at the failure
everyone actually complains about: the agent stayed inside its assigned scope
and still broke something.

The instinct is to enumerate the forbidden. Don't touch auth. Don't change the
response shape. Don't alter the schema. The list grows after every incident and
never closes — **because the set of forbidden behaviors is infinite.** You are
enumerating the complement of what you want, and complements of useful sets are
unbounded.

Qualification inverts it. You don't list what must not happen; you assert what
must remain true, and you check it afterwards. "Fix null handling in `parse()`"
doesn't become "don't alter authentication." It becomes: null input returns an
error, the public signature is unchanged, every existing caller's test still
passes. A **finite** set of assertions, executable, and it covers failure modes
you never thought to forbid.

Finite beats exhaustive. That's the entire trick.

---

## The two things that are not levels

Both AI-generated taxonomies I've read on this topic get these wrong, and so do
several vendor posts. They're worth naming precisely.

### Integrity is a property, not a level

Signed logs, hash chains, append-only storage, timestamp attestation. Every
ranking I've seen crowns "cryptographic audit trail" as the summit of assurance.

It isn't a rung. **Signing a log tells you nothing new about what happened** —
only that the record wasn't altered afterwards. A signed V1 trace is still a V1
trace: proof that a call happened, now tamper-evident. Integrity is orthogonal
to the ladder. It hardens whichever level you're standing on, and you need it
exactly when your evidence will be contested. It never moves you up.

### A second model is a weak oracle, not a strong one

One taxonomy put "another AI as verifier" at level 7 and independent outcome
verification at level 4. That ordering is backwards.

The axis that matters is **how independent your oracle is from the thing that
did the work**: the agent itself (worthless) → a second model (correlated blind
spots, overlapping training, similar failure modes) → a deterministic script →
direct observation of the system of record. An LLM judge earns its keep on
questions with no deterministic oracle — is this summary faithful, is this tone
acceptable. It does not outrank looking at the database. Nothing outranks
looking at the database.

---

## Where the tools actually sit

| What it does | Level |
|---|---|
| LLM observability platforms (traces, spans, dashboards) | V1 |
| Data/AI monitoring platforms | V1 + upstream data quality |
| Signed receipt / proof-of-execution layers | V2, strong integrity |
| Enterprise governance & evidence platforms | V2–V3, strong integrity, regulated buyers |
| Verification-receipt consultancies | V4, delivered as a service |
| Scope-checking tools for coding agents | V3 approximated by file paths, partial V5 via tests |
| Agent identity / delegation (CIAM) | a different axis entirely |

That last row deserves a sentence. Verifying *who* the agent is and verifying
*what it did* are different problems, and the current discourse blends them
daily. You need both. Buying one while believing you bought the other is how you
end up with a beautifully authenticated identity attached to entirely unverified
actions.

---

## Verify your verifier

Whatever level you pick, one rule outranks the ladder itself: **feed your
checker a run you know is bad, and watch it fail that run.** An untested
verifier is a belief with a dashboard.

Two failures from my own tool. I shipped both. I fixed both later, which is the
only reason I get to write about them calmly.

**The verifier trusted the thing it was verifying.** My escalation check — "did
the agent escalate when its mandate required it?" — read a trace attribute
called `alfred.escalated`. Written by the agent. So an agent that never
escalated could set one boolean and disarm the exact check pointed at it. The
fix was to stop honoring the declaration and count actual calls to the mandate's
escalation tools: an escalation is proven by an action, never by a flag the
agent pins on itself. That's the oracle-independence axis collapsing inside a
single bug — my oracle was the defendant.

**Silence read as success.** A tool call carrying no tool name was quietly
skipped by the allowlist check. Meaning: drop one attribute, and any call walks
past the mandate unexamined. The rule is now inverted — a call that cannot be
named cannot be allowed. An unverifiable call is a finding, not a blank.

Both bugs have the same shape, and it's the shape to hunt for in your own
checks: **the verifier reported a clean run because it couldn't see, not because
there was nothing to see.** An absence of findings and a finding of absence are
different results. Most verifiers silently conflate them.

So attack your checker before you trust it. Hand it the run you know is rotten.
If it comes back green, you haven't built a verifier. You've built a formality.

---

## How to choose

Pick by what you risk, not by what your stack makes convenient:

- **Nothing irreversible happens** → V1 is fine.
- **Someone must answer for the agent's behavior** — a client, an auditor, a
  regulator → **V3 is the floor.** A trace with no declared requirement behind
  it is not an audit trail; it's a log file with good marketing.
- **Money, or anything you can't undo** → V4, with an oracle that owes the agent
  nothing.
- **Broad autonomy over a system you care about** → V5.
- **Your evidence will be contested** → add integrity to whichever level you
  chose.

---

I build [Alfred](https://github.com/adriencr81/Check-Alfred), an Apache-2.0
Python package covering V1 to V3: it reads an agent's OpenTelemetry GenAI spans,
holds them against a mandate declared in YAML, and computes a daily digest in
which every statement is anchored to a trace event ID. Failed tool calls get
their own line, whatever the agent claimed about them.

![14-second terminal demo: a mandate forbids refunds above €100, the agent issues a €250 refund anyway, and alfred watch flags the deviation anchored to its trace event ID.](https://raw.githubusercontent.com/adriencr81/Check-Alfred/main/docs/assets/alfred-demo.gif)

It does **not** do V4 — it reads traces, not your database — and it does not do
V5 today. I'd rather write that here than have you discover it in production.

If you're verifying agents in production, I genuinely want to know which level
you stopped at, and why. That's the part nobody publishes.

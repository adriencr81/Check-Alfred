# Security policy

Alfred's job is to report what an AI agent actually did. A bug that lets an
agent shape its own report is not a cosmetic defect — it defeats the product's
one guarantee. Reports of that kind are welcome and taken seriously.

## Reporting a vulnerability

**Please don't open a public issue.** Use GitHub's private vulnerability
reporting on this repository: **Security → Report a vulnerability**. It opens a
private thread with the maintainer, so a working exploit doesn't sit in public
before there's a fix.

What helps most, in order: the version or commit, a minimal trace file or
mandate that reproduces it, and what you expected the digest to say versus what
it said. A proof-of-concept that makes the report lie is worth more than a
description of a mechanism.

Expect an acknowledgement within **72 hours** and an assessment within a week.
Alfred is maintained by one person alongside other work — if a fix will take
longer than that, you'll be told where it stands rather than left waiting.
Credit in the changelog on request.

## Supported versions

Pre-1.0, only the latest released version is supported. Fixes ship in a new
patch release; there are no backports to earlier 0.x versions.

## What's in scope

The threat model treats **the audited agent as the adversary**: it writes the
trace Alfred reads, so anything it can put in a span is untrusted input. In
scope, with the rounds that established each area:

- **Defeating a mandate check** — a tool call, argument, cost or escalation that
  should raise a deviation and doesn't (ADR 0023).
- **Forging or corrupting report content** — trace-derived text that alters what
  a manager reads in Slack, stdout or the HTML report; rewriting stored evidence
  a past digest already quoted (ADR 0026).
- **Breaking the anchoring rule** — any path that gets an assertion into a
  report without a real source event ID behind it, including a narration that
  cites a genuine event while claiming something the line doesn't say.
- **Leaking what Alfred holds** — declared `redact:` fields reaching the store
  or a sink in clear text, credentials (Slack webhook, LLM API key) escaping to
  disk, to another local account, or to another host (ADR 0025).
- **Stopping the auditor** — input that kills `alfred watch`, or makes it skip
  traces while reporting success (ADR 0024).

## What's out of scope

- **An agent that escapes its instrumentation.** Alfred reports what the trace
  records. Work done outside any traced span is invisible to it, by
  construction — this is a documented limit, not a vulnerability.
- **A wrong-but-confident agent.** A tool that returns garbage with a success
  status, or a model that answers incorrectly within its mandate, leaves no
  signal in the trace. Alfred won't claim what it can't anchor.
- **`chmod` on Windows.** Owner-only file modes are a POSIX floor; real
  protection there comes from NTFS ACLs (see `src/alfred/_fs.py`).
- Vulnerabilities in third-party packages with no Alfred-specific impact —
  report those upstream.
- Findings from a scanner with no demonstrated impact on the guarantees above.

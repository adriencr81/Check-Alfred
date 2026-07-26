# Alfred for teams

Alfred is Apache-2.0 and stays that way. Everything you need to point it at your
agents, compute an anchored digest and ship it to Slack is in the package, with
no tier gate and no seat count.

This page is about the other half, announced up front rather than discovered
later: **an advanced mandate engine is planned as closed-source**. If your
situation is on this page, we want to hear about it before it is built.

---

## What the open package already does

Worth checking first — most needs are already covered, and the answer to "can
Alfred do X for my team?" is more often yes than not:

- A declarative mandate in YAML, linted (`alfred mandate lint`) and versioned in
  your own repository.
- Typed deviations computed from traces, never self-reported.
- A daily digest in Slack, on stdout, or as a self-contained HTML report you can
  forward to whoever is accountable.
- Unattended daily runs via `alfred schedule --github-actions` — no server.
- PII redaction at ingestion (`redact:` in the mandate), before values reach the
  store.
- Your traces never leave your infrastructure. The package sends nothing home:
  there is no telemetry in Alfred, by design.

## What is planned as closed-source

Not available today, and no date is promised. Listed so you know where the line
falls:

- **Formal verdict semantics** — mandates that resolve to a defensible verdict,
  not just a list of flagged events.
- **Verifiable policies** — policy as a checkable artifact rather than a
  configuration file.
- **Multi-agent** — fleets, delegation between agents, responsibility across an
  agent chain.
- **Retention** — evidence kept and queryable over regulatory horizons.
- **Compliance** — the evidence-file export that turns a digest history into a
  reviewable record.

## If this is your problem, tell us

There is no waitlist, no pricing page and nothing to sign. What is useful right
now is the shape of the actual need — which of the above matters to you, on how
many agents, and what you are accountable for.

**[Open a teams inquiry →](https://github.com/adriencr81/Check-Alfred/issues/new?template=teams_inquiry.md)**

It is a public GitHub issue, so write only what you can share publicly; say so
in the issue if you need a private channel and we will find one. These inquiries
are read as the primary signal of what to build past v0.1 — a described need
weighs considerably more here than a star.

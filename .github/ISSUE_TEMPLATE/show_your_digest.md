---
name: Show your digest
about: You pointed Alfred at a real agent — show us what it computed
title: "Digest: "
labels: show-your-digest
---

**Your digest** (paste the stdout table, the Slack message or the HTML report —
whatever you got)

```
paste here
```

⚠️ A digest quotes your agent's real tool names and argument values. Redact
anything you can't post publicly — or run with a `redact:` list in the mandate
next time, which masks named arguments at ingestion, before they reach the
store (see `docs/adr/0022-pii-redaction.md`).

**What is the agent?** (framework, roughly what it does)

**Did Alfred catch anything you didn't already know?** This is the part we
learn the most from — including "no, it told me what I expected".

**What did the mandate look like?** (the `allowed_tools` / `daily_budget_eur`
you declared, if you can share them)

**Anything that got in the way** between `pip install` and this digest?

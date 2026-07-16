#!/usr/bin/env bash
# PreToolUse guardrail on Bash: deny destructive commands outright.
# Non-negotiable per CLAUDE.md — hooks are enforced 100% of the time, unlike
# prose instructions. Only covers broad/irreversible patterns; narrow,
# scoped commands (e.g. rm -rf ./build) are left to normal permission flow.
set -euo pipefail

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"

if [ -z "$command" ]; then
  exit 0
fi

deny_reason=""

if printf '%s' "$command" | grep -Eq '(^|[;&|]|&&)\s*rm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+(/|~|\$HOME|\.{1,2}|\*)(\s|$)'; then
  deny_reason="rm -rf sur une cible large (/, ~, ., .., *) bloqué par le hook projet."
elif printf '%s' "$command" | grep -Eq '\bgit\s+push\b[^|;&]*(--force\b|-f\b)'; then
  deny_reason="git push --force/-f bloqué par le hook projet — demande confirmation explicite."
elif printf '%s' "$command" | grep -Eq '\bgit\s+reset\s+--hard\b'; then
  deny_reason="git reset --hard bloqué par le hook projet — peut écraser du travail non committé."
elif printf '%s' "$command" | grep -Eq '\bgit\s+clean\s+-[a-zA-Z]*f'; then
  deny_reason="git clean -f bloqué par le hook projet — supprime des fichiers non trackés."
elif printf '%s' "$command" | grep -Eq '\bgit\s+(checkout|restore)\s+(--\s+)?\.(\s|$)'; then
  deny_reason="git checkout/restore . bloqué par le hook projet — écrase les modifications locales."
fi

if [ -n "$deny_reason" ]; then
  jq -n --arg reason "$deny_reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
fi

exit 0

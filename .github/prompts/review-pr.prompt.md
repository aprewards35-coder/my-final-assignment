---
name: review-pr
description: "Launch a pinned, evidence-based PR review with explicit inputs and inspection-only defaults."
---

# Review a pinned PR

Explicitly read and apply the
[evidence-based PR review skill](../skills/evidence-based-pr-review/SKILL.md).
Report that you read it; do not claim automatic discovery.

## Establish inputs

Use inputs supplied with this invocation. Ask only for missing required inputs:
- Repository: OWNER/REPO.
- PR number.
- Expected full head SHA.
- Scope: default to the complete PR diff.
- Optional historical base SHA.
- Optional authorized execution: default to none.

Do not derive a new task from a historical prompt or silently reuse an earlier
review target. If asked to resolve the current head, retrieve and present it
for confirmation before beginning substantive review.

## Verify before reviewing

Read applicable AGENTS.md instructions and establish the workspace/repository
location explicitly; do not assume the terminal starts in the repository.

For a current PR, verify published head repository, branch, full SHA, and base.
Stop on an expected-head mismatch. Record the actual comparison and merge base.

For a historical review, require an exact head and base. Verify their availability
and inspect that comparison rather than substituting the PR's current state.
Label current GitHub metadata separately from historical evidence.

Record local HEAD and working-tree changes. Do not switch branches, fetch, or
create worktrees without separate authorization. A differing local checkout
does not authorize attribution of its files or results to the requested target.

If required evidence is unavailable, report the limitation and stop where it
prevents a grounded review.

## Permissions

This invocation authorizes source-text inspection and read-only Git/GitHub
metadata and existing-log queries only.

Do not edit, stage, install dependencies, commit, push, post comments, request
reviewers, or change PR/issue state. Do not read secrets or change authentication.

Do not run tests, import application/dependency modules, execute repository
scripts or hooks, invoke providers/graders, or start workflows.
The evidence collector is not automatically authorized.

If execution would resolve a material uncertainty, propose exact bounded
commands, effects, and interpretation, then wait for separate approval.

These are instructions, not a technical sandbox or credential restriction.

## Perform and report

Perform one substantive review using the skill. Do not require a second agent
pass by default. Propose targeted reconciliation only for material unresolved
questions or conflicting evidence.

Report:
- Supplied inputs and verified head/base/comparison.
- Skill path and, where obtainable, its content fingerprint or committed version.
  Label uncommitted skill content explicitly.
- Inspection coverage, findings, evidence map, and limitations.
- Commands actually executed and any deviations from these permissions.
- Remaining acceptance steps without claiming approval or evaluation readiness.

Do not create a review archive or post the report automatically. Return the
report in chat. Propose preservation separately when useful.

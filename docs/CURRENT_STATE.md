# Current state of the project
---

Status: Phase A complete; B1–B4 documented as passed; B5/B6 characterization integrated; partial offline evaluation tooling merged and accepted. Issue #12 assessment complete: not evaluation-ready; execution remains blocked and unauthorized. No B5/B6 production correction is included.
Status reconciled: 2026-11-01
Reviewed: 2026-10-22
Baseline reviewed: [`7d6513a`](https://github.com/aprewards35-coder/my-final-assignment/commit/7d6513a)
Verification base checkout (historical; 2026-10-22, before the A2 documentation patch):
`593eb10eab7273e3f55408233588db646081062b`
Historical verification context: the checkout above predates the A2
documentation patch. Current completion evidence is recorded below.

---

This document consolidates project status, accepted decisions, and historical
verification at the revisions identified in each section. The original
reviewed baseline above is distinct from the selected pre-change evaluation
baseline below. It does not establish that every requirement is implemented
or verified.

## Status reconciliation — 2026-11-01

- B6 characterization was integrated through [PR #11](https://github.com/apeaircreative/my-final-assignment/pull/11)
  on 2026-10-26 at `638f565693ce3740855878033d8fd6183d803760`.
  Integration does not establish real-provider cancellation or a production
  lifecycle correction.
- Partial offline controls and compatibility tooling merged through
  [PR #18](https://github.com/apeaircreative/my-final-assignment/pull/18) at
  `fbbc5547fdc53e3853f54c4949952b67607c4b2c`.
- [Review reconciliation](https://github.com/apeaircreative/my-final-assignment/pull/18#issuecomment-6559504240)
  and [owner acceptance](https://github.com/apeaircreative/my-final-assignment/pull/18#issuecomment-6559576782)
  are complete for the partial scope. The owner disclosed control of both
  accounts; this is not independent second-person approval.
- [Issue #12's final assessment](https://github.com/apeaircreative/my-final-assignment/issues/12#issuecomment-6559721999)
  is complete and the issue is closed with a not-ready / execution-blocked
  outcome, not verified end-to-end execution readiness.
- Remaining readiness gates are preserved in
  [#14](https://github.com/apeaircreative/my-final-assignment/issues/14#issuecomment-6559721538) and
  [#15](https://github.com/apeaircreative/my-final-assignment/issues/15#issuecomment-6559721747).
  [#13](https://github.com/apeaircreative/my-final-assignment/issues/13) remains the fresh-case prerequisite.
- No evaluation candidate is frozen. Real-provider completion/stop, hard
  aggregate enforcement, a complete approved execution path, and exact
  future-candidate compatibility remain unresolved readiness requirements.
- Recorded verification retains its original revision context. This status
  update claims no new test or grader execution. Live evaluation remains
  unauthorized.

## Status reconciliation — 2026-10-26

Evidence observed at `2026-10-26T18:19:59Z`:

- Selected pre-change evaluation baseline:
  `da5776412fe0c200201032726b7db4a2f0cce954`.
  Local Git inspection confirmed it is an ancestor of the recorded merge.
- PR #1 merged on 2026-10-22 at
  `9a076d4bd142d802a7fbb20ac6b2e5f0e39a82b2`.
  This is the merged revision, not automatically the final evaluation candidate.
- Post-merge `check` run `39829635839` completed successfully.
- CodeQL Advanced runs `39829635845` and `40194532300` completed successfully
  at the same merged revision. Workflow success does not establish absence
  of findings.
- The owner reports final review and CodeQL follow-up complete.
  The PR review API returned no formal review objects; this does not
  establish that no review occurred. Code Scanning findings were not
  independently inspected in this reconciliation.
- Phase A milestone #1 is closed; Phase B milestone #2 is open.
- The README links the current-state summary, application contract, and
  gap-closing plan. The root AGENTS.md contains the contract-work pointer.

Workflow evidence:

- https://github.com/apeaircreative/my-final-assignment/pull/1
- https://github.com/apeaircreative/my-final-assignment/actions/runs/39829635839
- https://github.com/apeaircreative/my-final-assignment/actions/runs/39829635845
- https://github.com/apeaircreative/my-final-assignment/actions/runs/40194532300

No tests, live-model calls, or graders were run locally for this
documentation reconciliation. PR validation runs separately in GitHub
Actions; its job status alone does not establish a live-model result
or a practice-grader score.
Historical verification results below retain their original revision and
working-tree context. This update does not establish improved live-model
or private-grader performance.

## Historical verification before A2 documentation patch

On 2026-10-22, the offline test-job commands from
[`.github/workflows/check.yml`](../.github/workflows/check.yml) were run at
base checkout `593eb10eab7273e3f55408233588db646081062b` with
`BOOTCAMP_PROVIDER=fake`:

- `BOOTCAMP_PROVIDER=fake uv sync --locked` — exit 0.
- `BOOTCAMP_PROVIDER=fake uv run ruff check .` — exit 0.
- `BOOTCAMP_PROVIDER=fake uv run pytest` — exit 0; 42 passed in 0.34s.

The workflow configures Python 3.11. These fake-provider checks verify offline
behavior only; they do not measure live-model answer quality. No live provider,
practice grader, or private questions were used. GitHub-hosted CodeQL results
were not inspected here.

The 42-pass result above is historical for this base checkout. At the
2026-10-22 local review worktree, after adding the quote-diagnostic regression test,
`BOOTCAMP_PROVIDER=fake uv run ruff check .` passed and
`BOOTCAMP_PROVIDER=fake uv run pytest` reported 43 passed. These local results
do not update the historical run records or imply additional PR CI.

The two retained P3 artifacts were compared on per-case answers, retrieved
content, and grader dimensions; those inspected fields matched. The selected-
case artifacts were also checked: baseline `fa-07` has two distinct answers
across its repeats, and item-detail `fa-05` has two distinct answers with
outcomes false/true/true. These artifact observations do not establish general
determinism, answer correctness, or private-grader performance.

## What the system is

A bounded, source-grounded research assistant. `YourAgent` in
[`agent.py`](../agent.py) answers developer questions using six versioned
documents in [`data/corpus/`](../data/corpus/).

Its intended behavior is to cite retrieved sources and refuse questions the
corpus does not support. Enforcement is narrower than that product goal.
Accepted requirements and known gaps are recorded in
[APPLICATION_CONTRACT.md](APPLICATION_CONTRACT.md).

### Ownership boundaries

The pinned course dependency owns:

- Retrieval and context construction.
- Strict-JSON parsing with at most one repair retry.
- Citation-ID normalization and verification against retrieved document IDs.

The application wrapper owns:

- The source-terminology prompt extension.
- Per-call timeout handling.
- Provider-failure refusal traces.
- Review-to-refusal conversion.
- The post-generation instruction-pattern check on retrieved content.

The course dependency is pinned to commit:

`1de8649529156c35bdeafacfbbef40726a9b0fba`

### Execution shape

The supported answer path is a fixed retrieve-then-generate chain:

- No retrieved chunks: refuse without calling the model.
- Retrieved chunks: one model call.
- Invalid response format: at most one repair call.

The registered tools are not invoked by `YourAgent.run()`. The
`max_tool_calls=3` argument is accepted but unused by the pinned course
answer pipeline. It must not be described as an enforced tool budget on
this execution path.

## Reported verification and experimental evidence

These results belong to their recorded revisions and configurations.
They are not automatically measurements of a later working tree.

### Offline tests

The historical full-suite result at the pre-A2 verification checkout was
42 passed. The later 2026-10-22 local review result was 43 passed, as recorded
above. These are offline fake-provider results, not live-model quality measures.

### Historical public practice report

The preserved
[2026-10-19 report](../score_report_qwen25_7b_instruct_baseline_2026-10-19.json)
records:

- 5/10 passed.
- Critical gate failed.
- Critical refusal case `fa-09` failed.

This summary artifact contains answer hashes and gate results, not complete
answer text, retrieved passages, or execution traces.

### Top-k experiments

No tested setting established a stable winner across the recorded comparisons.
`top_k=4` remains the conservative existing default, not a proven optimum.

Provider-failure attempts must remain excluded from model-quality comparisons.

### Sampling and prompt corrections

The experimental Ollama request shape was corrected from nested `options`
to top-level sampling fields.

The prompt extension was corrected to use actual line breaks rather than
literal backslash-n characters. A regression test covers that separator.

Historical runs must retain their original configuration caveats. A later
correction does not retroactively validate earlier settings.

### Prompt experiments

The reported results are:

| Experiment | Result | Interpretation |
|---|---|---|
| Broad coverage instruction | 0/6 | Rejected wording for the tested condition |
| Corrected-source selected-case comparison | Baseline 3/6; item-detail 5/6 | Promising selected-case signal, not general validation |
| P3 full public-set comparison | Baseline 5/10 with critical fail; item-detail 6/10 with critical pass | Public-practice regression evidence, not private-grader evidence |

The two retained P3 artifacts were compared directly. Their inspected per-case
answers, retrieved content, and grader dimensions match. This finding applies
only to these two artifacts and is not a claim of general determinism.

P3 artifacts are retained under
[`runs/public-prompt-comparison/`](../runs/public-prompt-comparison/).

The P3 repeat is a different experiment from the corrected-source
selected-case comparison. Their repeatability claims must not be conflated.

### Prompt decision

Keep the baseline prompt as the default.

The item-detail instruction remains a preserved candidate, not an adopted
application change. Future adoption requires a newly authored, independently
reviewed evaluation set and a frozen comparison protocol.

The six-question exploratory set and eight-question P2 set are consumed
evaluation material, not untouched holdouts.

## Accepted application decisions

The accepted contract is recorded in
[APPLICATION_CONTRACT.md](APPLICATION_CONTRACT.md).

In summary:

1. `YourAgent.run()` and its delegating `__call__()` are the supported
   hardened interfaces.
2. A substantive answer must retain at least one valid retrieved citation;
   otherwise return the standard flagged refusal.
3. Model-requested review requires refusal, even when citation sanitization
   also occurs. Sanitization-only review may preserve a cleaned answer
   only when at least one valid citation remains.
4. Retain the post-generation retrieved-content check. Its guarantee
   concerns the returned answer for detector matches, not prevention of
   model exposure or comprehensive injection detection.

Acceptance does not mean these requirements are already implemented.

## Detector characterization

The reviewed detector:

- Matches configured exact phrases, including those inside benign quotes.
- Matches some regex variants.
- Excludes regex-only matches when a quote directly precedes the matched
  instruction.
- Misses other phrasings, such as "ignore your instructions".
- Does not match the corpus's own quoted example under the reviewed wording.

The check runs after generation. Existing injection tests verify that the
instruction reaches the controlled model and that the returned answer is
overridden for the tested matching content.

They do not prove that the model was protected from exposure, or that
unmatched attacks are rejected.

Preserve executable boundary tests and their actual output rather than
relying only on a prose characterization.

## Documentation reconciliation checklist

- [x] Verify the offline test-job commands and passing outcome at this checkout.
- [x] Inspect both P3 artifacts and compare the recorded per-case fields.
- [x] Replace stale README P3 wording and the old test count.
- [x] Correct selected-case repeatability statements in `docs/extra.md`.
- [x] Link the current-state summary, accepted contract, and gap-closing plan
  from the README.

A2 status: complete. See the dated status reconciliation above for merge,
workflow, owner-reported review, and CodeQL evidence limits.

### Selected-case repeatability correction

The corrected-source comparison artifacts establish variation in:

- Item-detail `fa-05`: repeat 1 differs from repeats 2–3 and has a different
  `claim_support` outcome.
- Baseline `fa-07`: repeat 1 differs from later repeats.

The updated `docs/extra.md` records these differences and the item-detail
`fa-05` pass pattern (false/true/true), without conflating them with the P3
artifact comparison.

Keep this correction separate from the P3 comparison: its two artifacts matched
on the inspected per-case answers, retrieved content, and grader dimensions.

## Remaining work

Follow [GAP_CLOSING_PLAN.md](GAP_CLOSING_PLAN.md) sequentially.

- Phase A: complete; milestone #1 is closed. See the dated evidence above.
- Phase B: B1–B4 are documented as passed. B5 / issue #6 characterization
  is integrated in merge `23023a6d4713b89d84d4bb93fdcb1e0194afa009`;
  its trace-fidelity gap remains unresolved. B6 / issue #7 local timeout
  characterization passed; final review and PR integration remain pending.
  See the plan for revision-specific evidence and lifecycle limitations.
- Phase C: fix demonstrated contract violations with the smallest appropriate
  changes.
- Subsequent quality evaluation: use a freshly frozen protocol before
  quality-affecting experiments.

## Tracked limitations

See [ISSUES.md](ISSUES.md).

- The timeout bounds caller waiting but does not cancel the underlying
  provider worker.
- The memory/retention contract remains incompletely demonstrated.
- Citation-ID validation is not semantic claim verification.
- The detector is deliberately narrow.

No model evaluation, test execution, or implementation change is established
merely by adding this document.
# Gap-closing plan
---

Status: sequential implementation plan
Created: 2026-10-21
Baseline reviewed: [`7d6513a`](https://github.com/aprewards35-coder/my-final-assignment/commit/7d6513a)

---

## Purpose

Turn the accepted application decisions into executable offline checks,
identify demonstrated violations, and make the smallest appropriate fixes.

Policy source:
[APPLICATION_CONTRACT.md](APPLICATION_CONTRACT.md)

Evidence snapshot:
[CURRENT_STATE.md](CURRENT_STATE.md)

## Scope boundaries

Unless separately approved:

- No live model calls or Ollama runs.
- No public or private grader runs.
- No prompt tuning or top-k changes.
- No retrieval redesign or new dependencies.
- No corpus edits.
- No modification of historical run artifacts.
- No promotion of teaching helpers to supported interfaces.
- No automatic commits.

Inspect the current checkout and unrelated worktree changes before editing.
Do not assume the working tree still matches the reviewed baseline.

## Workflow

For each task:

1. Read the relevant accepted rule and current implementation.
2. Check whether existing tests already cover it.
3. Define the expected behavior before editing.
4. Add the smallest focused test.
5. Run the focused test and full offline suite.
6. Record actual results and review the diff.
7. Stop before a production fix if the test exposes a violation.
8. Approve the smallest fix separately.
9. Verify the regression and review before committing.

### Passing and failing tests

A characterization test records an observed boundary and may pass immediately.

An accepted-requirement test may fail because the requirement is not yet
implemented. A failure is evidence, not permission to weaken the requirement.

Do not leave a blocking failing test on the normal integration branch without
an explicit workflow decision. Keep the failing result as evidence on the
working branch; after review, pair the test with its approved correction
before merging or committing to a branch expected to remain green.

## Phase A — Documentation and evidence reconciliation

### A1 — Record accepted decisions

Status: complete; accepted contract, README links, and AGENTS.md pointer are present in merged revision `9a076d4bd142d802a7fbb20ac6b2e5f0e39a82b2`.

Tasks:

- Add the accepted application contract.
- Clearly distinguish accepted policy from implemented behavior.
- Identify supported and excluded interfaces.
- Link these documents from the README.
- Add a short pointer in AGENTS.md without duplicating the contract.

Completion condition:

The repository contains one unambiguous statement of the accepted rules.

### A2 — Reconcile reported results

Status: complete; documentation work merged in PR #1. Post-merge check and CodeQL workflows succeeded; final review and CodeQL follow-up are owner-reported complete. See CURRENT_STATE.md for dated evidence and limits.

Tasks:

- Verify test collection counts and passing outcomes.
- Read both complete P3 artifacts.
- Verify reported baseline and candidate results.
- Verify the cross-run answer, retrieval, and grader-outcome identity claim.
- Correct the README's stale P3 status and test count.
- Correct the selected-case repeatability statement in docs/extra.md.

Completion condition:

The current-state summary and existing documentation agree with the retained
evidence. Historical results remain attached to their recorded revisions.

## Phase B — Offline verification

Complete one task at a time.

### B1 — Supported-interface delegation

Status: passed

Contract: Q1

Requirement:

Calling the agent forwards the unchanged question to that instance's run()
exactly once and returns result.answer.

Proposed test:

test_call_delegates_to_run_and_returns_its_answer

Allowed changes:

tests/test_contract.py only.

Implementation instruction:

> Read AGENTS.md, agent.py, and tests/test_contract.py.
>
> Inspect the worktree and report unrelated changes. Check whether an existing
> test already verifies this exact delegation behavior; do not duplicate it.
>
> If coverage is missing, instantiate YourAgent with the existing FakeLLM.
> Construct a valid ResearchAnswer and AgentResult using the actual types.
> Replace run on that specific instance with a recording stub returning the
> constructed result.
>
> Call the agent with a fixed question. Assert that the stub receives exactly
> that question, exactly once, and that the returned object is result.answer.
>
> Do not invoke retrieval, a real provider, Ollama, a grader, or a network
> service. Do not change production code or add xfail/skip markers.
>
> Run the focused test, full offline suite, and git diff --check. Show the
> diff, actual command outcomes, and final worktree status. Do not commit.
> If the test fails, explain the failure and stop before fixing production
> code.

Completion condition:

Direct delegation is covered by a passing isolated test, or existing
equivalent coverage is identified and documented.

### Outcome

Status: passed

Implementation commit: `3a8ac9420769a5fb71abe5939e9acc552efa8e02`

Revision checked during verification:
`3a8ac9420769a5fb71abe5939e9acc552efa8e02` (same as the implementation
commit).

Commands and actual outcomes:

- Focused test: `uv run pytest tests/test_contract.py::test_call_delegates_to_run_and_returns_its_answer` — 1 passed.
- Full offline suite: `BOOTCAMP_PROVIDER=fake uv run pytest` — 24 passed.
- Diff check: `git diff --check` — passed with no output.

Changed files:

- `tests/test_contract.py` (implementation commit).

Evidence or limitation:

`test_call_delegates_to_run_and_returns_its_answer` verifies unchanged
question forwarding, exactly one call to that instance's `run()`, and return
of the same `result.answer` object. Delegation coverage does not independently
verify Q2–Q4 or timeout behavior.

Reviewed: 2026-10-21.

Commit: `3a8ac9420769a5fb71abe5939e9acc552efa8e02`.

### B2 — Missing-citation requirement

Status: passed

Contract: Q2

Cases:

- A substantive model answer supplies no citations and requests no review.
- Sanitization removes every supplied citation.

Required outcome:

The standard flagged refusal.

Completion condition:

Focused tests demonstrate compliance or expose the exact contract violations.

### Outcome

Status: passed

Tested HEAD: `e843309b20790e9f3a42f520a62bfb29e0220975`.

Working-tree changes present during verification: uncommitted changes to
`agent.py` and `tests/test_contract.py`. The test and implementation changes
were not part of the tested HEAD; no commit SHA is assigned to them here.

Before the correction, the two focused Q2 tests failed and the full offline
suite reported 2 failed, 24 passed. After the correction:

- Focused Q2 tests: `BOOTCAMP_PROVIDER=fake uv run pytest tests/test_contract.py::test_uncited_substantive_answer_returns_standard_refusal tests/test_contract.py::test_all_citations_removed_returns_standard_refusal` — 2 passed.
- Partial-sanitization regression: `BOOTCAMP_PROVIDER=fake uv run pytest tests/test_contract.py::test_citation_retrieval_never_returned_is_stripped_and_flagged` — 1 passed.
- Full offline suite: `BOOTCAMP_PROVIDER=fake uv run pytest` — 26 passed.
- Diff check: `git diff --check` — passed.

Changed files:

- `agent.py`
- `tests/test_contract.py`

Evidence or limitation:

The correction is in the application wrapper, after the existing
instruction-content check and before the citation-sanitization review
exception. It preserves the course trace, including citation-sanitization
events, and appends a missing-citation decision when converting an uncited
result. An already-standard refusal is returned unchanged. The regression
tests are `test_uncited_substantive_answer_returns_standard_refusal` and
`test_all_citations_removed_returns_standard_refusal`. The existing partial
citation-sanitization test remains passing. This verifies the citation
requirement, not semantic claim support. Q3 mixed-review provenance remains
unresolved and was not changed by B2.

Reviewed: 2026-10-21.

### B3 — Review-reason combinations

Status: passed

Contract: Q3

Cases:

- Model requests review with valid citations.
- Model does not request review; sanitization removes an invalid citation
  while a valid one remains.
- Model requests review and sanitization also occurs.
- Sanitization removes all citations; reuse B2 coverage where appropriate.

Required outcomes:

Match the accepted Q3 disposition table.

Additional investigation:

Determine whether the returned course interface preserves the model's
original review reason. Do not infer provenance solely from the final flag.

Completion condition:

Each disposition is exercised, and any interface limitation is explicitly
recorded before choosing a fix.

### Outcome

Status: passed

Tested HEAD: `7c193fb3397f93333313d6ab3ed550b0e11645a9`.

Working-tree changes present during verification: uncommitted changes to
`agent.py` and `tests/test_contract.py`. The implementation and test changes
were not part of the tested HEAD; no commit SHA is assigned to them here.

Commands and actual outcomes:

- Focused Q3/observer cases: `BOOTCAMP_PROVIDER=fake uv run pytest tests/test_contract.py::test_model_requested_review_returns_standard_refusal tests/test_contract.py::test_model_requested_review_with_sanitization_returns_standard_refusal tests/test_contract.py::test_citation_retrieval_never_returned_is_stripped_and_flagged tests/test_contract.py::test_parse_repair_uses_review_flag_from_valid_response tests/test_contract.py::test_review_observation_is_isolated_between_runs tests/test_contract.py::test_unknown_review_provenance_returns_standard_refusal tests/test_contract.py::test_two_parse_failures_preserve_course_refusal_without_provenance_event` — 9 passed.
- Q2 plus refusal/provider-error/timeout checks: `BOOTCAMP_PROVIDER=fake uv run pytest tests/test_contract.py::test_uncited_substantive_answer_returns_standard_refusal tests/test_contract.py::test_all_citations_removed_returns_standard_refusal tests/test_contract.py::test_refusal_for_an_unsupported_question_costs_zero_model_calls tests/test_contract.py::test_provider_error_is_flagged_not_raised tests/test_contract.py::test_timeout_on_a_hanging_provider_is_flagged_within_a_second` — 5 passed.
- Full offline suite: `BOOTCAMP_PROVIDER=fake uv run pytest` — 34 passed.
- Diff check: `git diff --check` — passed.

Changed files:

- `agent.py`
- `tests/test_contract.py`

Evidence or limitation:

The request-scoped observer uses the exact course `parse_research_answer`
function, retains only the original parsed review boolean, and is constructed
locally for each `YourAgent.run()`. It sits outside `TimeoutClient`; timeout
cancellation and concurrent-provider safety are not established. The repair
tests verify that invalid first output is rejected and the valid repair's
review flag controls disposition. Successive-run tests verify outcomes;
request-local construction is also established by code inspection. The
unknown-provenance fallback test uses a controlled local test seam rather
than the ordinary pipeline. The tests verify that model-requested review
refuses with and without citation sanitization, while sanitization-only
review with a surviving valid citation preserves the cleaned, low-confidence,
flagged answer. Two parse failures preserve the course's canonical refusal
without a provenance-failure decision. These are offline checks, not
live-model quality evidence. At this historical verification point, Q4 boundary coverage remained pending; see the subsequent B4 outcome.

Reviewed: 2026-10-21.

### B4 — Detector boundaries and returned-answer override

Status: passed

Contract: Q4

Tasks:

- Add direct offline characterization cases for exact phrases, benign quotes,
  regex variants, and known misses.
- Preserve a clear distinction between detector unit tests and answer-path
  integration tests.
- Reuse existing integration coverage where it already verifies exposure
  followed by a returned refusal.
- Do not broaden the detector or move the check during characterization.

Completion condition:

Tests show the matching boundaries and the supported path's response to a
match without claiming comprehensive injection protection.

### Outcome

Status: passed

Tested HEAD: `d21895acb2e8d737113e3f7ae9b3ba1d15ea01f8`.

Working-tree changes present during verification: uncommitted changes to
`tests/test_contract.py`; the B4 test changes were not part of the tested
HEAD. No commit SHA is assigned to them here.

Collection reconciliation: `BOOTCAMP_PROVIDER=fake uv run pytest --collect-only -q`
reported 36 cases in `tests/test_contract.py`, 2 in
`tests/test_controlled_cases.py`, and 4 in `tests/test_heldout_prompt_compare.py`
(42 total). The focused selection reported 10 passed and 26 deselected.

Commands and actual outcomes:

- Focused detector and injection tests: `BOOTCAMP_PROVIDER=fake uv run pytest tests/test_contract.py -k "instruction_detector_characterization or prompt_injection_corpus_example_detector_characterization or injection_cannot"` — 10 passed, 26 deselected.
- Full offline suite: `BOOTCAMP_PROVIDER=fake uv run pytest` — 42 passed.
- Diff check: `git diff --check` — passed.

Changed file:

- `tests/test_contract.py`.

Evidence or limitation:

Seven direct detector characterization cases use pinned `Chunk` and
`ScoredChunk` inputs without retrieval. One additional test loads and scans
the entire versioned `prompt-injection` document as a constructed chunk. The
strengthened existing `test_injection_cannot_dictate_an_unflagged_answer`
verifies matching content reaches the controlled model, that it attempts an
`ACCESS GRANTED` answer, and that `YourAgent.run()` returns the canonical
refusal shape with the application instruction-content decision event.

Detector misses and quote-sensitive false positives remain. These
characterization expectations may change with an intentional detector
improvement; they are not permanent desired security requirements. The
integration test verifies the returned result, not prevention of model
exposure or comprehensive injection resistance. No live model, grader,
production behavior, or corpus changes occurred.

Reviewed: 2026-10-21.

Status update — 2026-10-26: The planned offline implementation/verification
tasks for Q1–Q4 (B1–B4) and Phase A A2 are complete. Reliability tasks B5/B6
remain pending as separately listed. Final review and CodeQL follow-up are
owner-reported complete; the dated reconciliation in CURRENT_STATE.md
records accessible evidence and its limits.

### B5 — Failure during parse repair

Status: violation demonstrated; controlled characterization executed and
desired diagnostic target approved on 2026-10-26. Local diff review
completed. Subsequent integration: PR #10 merged as
`23023a6d4713b89d84d4bb93fdcb1e0194afa009`; B5 / issue #6
completion and review satisfy B6's prerequisite.
No production correction is included.

Reliability target:

Preserve an accurate account of a malformed first response followed by a
failed repair call.

Controlled client:

- First complete() call returns malformed output.
- Second complete() call raises a supported provider exception.

Tasks:

- Inspect the returned trace.
- Record which completed and failed steps are preserved or lost.
- Specify the desired trace sequence before proposing a correction.

Completion condition:

An executable case establishes the behavior and any trace-fidelity violation.


### Outcome — B5 characterization, 2026-10-26

Status: violation demonstrated; desired diagnostic target approved.
Local diff review completed. Subsequent integration: PR #10 merged as
`23023a6d4713b89d84d4bb93fdcb1e0194afa009`; B5 / issue #6 is complete.

Verification base:
`5d079d2426013d9392377b1da24cde1ff987ae1b`, with uncommitted B5 test changes
in `tests/test_contract.py`. These changes were not part of the base commit.

Evidence observed at `2026-10-26T19:04:21Z`:

- The controlled client returned malformed output on the first call.
- Exactly two calls occurred; the second received the pipeline's repair
  instruction and raised `ConnectionError`.
- The supported application path returned the standard flagged refusal.
- Returned trace:
  `retrieve` -> `llm_call: provider call failed: ConnectionError` ->
  `decision: provider call failed; flagged refusal`.
- The returned trace omitted the initial completion and the parse-failure
  decision that triggered repair. Source inspection shows that the
  application exception handler constructs a replacement trace after the
  pipeline exits with an exception.

Initial verification:

- Focused characterization: 1 passed.
- Full offline suite: 44 passed in 0.64s.
- Ruff: passed.
- Initial diff check reported a trailing blank line in the added test.
  Whitespace was subsequently normalized.

Final local verification observed at `2026-10-26T19:10:59Z`, against
the same base revision with the B5 working-tree changes:

- Focused characterization: 1 passed.
- Full offline suite: 44 passed in 0.34s.
- Ruff: passed.
- `git diff --check`: passed.
- Local diff review: limited to the characterization test and its
  roadmap/issue documentation; no production changes.

Approved desired behavior:

Preserve enough truthful, ordered execution history to distinguish the
initial completion, parse failure and repair decision, failed repair call,
and final refusal. This does not prescribe exactly five events, specific
event names, or retention of raw prompts and responses.

Scope and remaining limitations:

- The passing characterization records a demonstrated gap; it does not fix it.
- No production code, dependency, corpus, or accepted answer policy changed.
- Any correction requires separate Phase C approval and compatibility review.
- No live model or grader was run locally for this characterization.
- Live-model quality, private-grader performance, timeout cancellation,
  and concurrent-provider safety are not established by this result.
- B5 completion and review subsequently satisfied B6's prerequisite;
  see the integration update above.

### B6 — Timeout boundaries

Historical local checkpoint: controlled characterization passed; local test and documentation
review completed. PR validation and integration were pending at that checkpoint;
see the 2026-11-01 integration reconciliation below.
B5 / issue #6 completion and review satisfy the prerequisite; its merged
characterization is present in base revision
`23023a6d4713b89d84d4bb93fdcb1e0194afa009`.
No production correction is included.

Tasks:

- Identify what existing tests establish about caller waiting.
- Distinguish waiting bounds from cancellation and worker cleanup.
- Preserve the tracked limitation unless a separate lifecycle fix is approved.
- Do not claim that a timely refusal proves provider cancellation.

Completion condition:

Tests and documentation accurately describe the enforced boundary and the
remaining lifecycle risk.

### Outcome — B6 characterization, 2026-10-26

Historical local checkpoint: controlled characterization passed; local test and documentation
review completed. PR validation and integration were pending at that checkpoint;
see the 2026-11-01 integration reconciliation below.

Verification base:
`23023a6d4713b89d84d4bb93fdcb1e0194afa009`, with the uncommitted B6
characterization in `tests/test_contract.py`. The added test was not part
of the base commit.

Source inspection:

- `TimeoutClient.complete()` starts a daemon provider worker and waits
  using `worker.join(timeout=self.timeout_s)`.
- If the worker remains alive after that wait, the wrapper raises
  `TimeoutError`; the supported application path catches it and returns
  a flagged refusal.
- The configured timeout applies to each wrapped provider-call wait,
  not to the entirety of `YourAgent.run()`.
- The inspected timeout path does not attempt provider cancellation or
  perform a subsequent join of the timed-out provider worker.

Existing coverage:

`test_timeout_on_a_hanging_provider_is_flagged_within_a_second` checks
caller completion within a one-second test window with `timeout_s=0.2`,
and a flagged refusal. It does not separately assert provider-operation
completion.

Added controlled evidence:

`test_timeout_returns_before_controlled_provider_operation_completes`
establishes that:

- The provider invocation starts.
- The caller returns within the one-second test window with the standard
  flagged refusal and a `TimeoutError` provider-failure trace event.
- The controlled provider operation remains incomplete at the post-return
  observation, before explicit release.
- After explicit release, the provider operation reaches its completion
  signal within the bounded cleanup window.
- The provider observes explicit release rather than defensive-wait expiry.

The test releases the controlled provider in a `finally` block. Its
provider wait and cleanup waits are bounded.

Commands and actual outcomes:

- Focused tests:
  `BOOTCAMP_PROVIDER=fake uv run pytest tests/test_contract.py::test_timeout_on_a_hanging_provider_is_flagged_within_a_second tests/test_contract.py::test_timeout_returns_before_controlled_provider_operation_completes`
  — 2 passed in 0.50s.
- Full offline suite: `BOOTCAMP_PROVIDER=fake uv run pytest`
  — 45 passed in 0.55s.
- Lint: `BOOTCAMP_PROVIDER=fake uv run ruff check .`
  — all checks passed.
- Diff check: `git diff --check` — no diagnostics.
- Initial results above preceded the supporting documentation edits.
- Final verification after documentation/status reconciliation:
  `BOOTCAMP_PROVIDER=fake uv run pytest` — 45 passed in 0.56s;
  `BOOTCAMP_PROVIDER=fake uv run ruff check .` — all checks passed;
  `git diff --check` — no diagnostics.
- The final evidence-record wording was updated afterward; the test
  and production code were unchanged.

Changed files in this B6 work:

- `tests/test_contract.py`
- `docs/GAP_CLOSING_PLAN.md`
- `docs/ISSUES.md`
- `docs/APPLICATION_CONTRACT.md` — status reconciliation only.
- `docs/CURRENT_STATE.md` — status reconciliation only.

Evidence limits and remaining risks:

- Caller return is distinct from provider-operation completion.
- A timely refusal does not establish provider cancellation.
- The provider completion signal does not establish internal worker-thread
  termination or comprehensive resource cleanup.
- Strict end-to-end timing guarantees, concurrent-provider safety, and
  production resource impact remain unestablished.
- The controlled continuation observation records a current limitation;
  it is not a requirement to preserve that limitation after an approved fix.
- No production correction, dependency change, corpus change, live-provider
  call, or grader run is included.
- No improved live-model quality or private-grader performance is claimed.
- Any lifecycle correction requires separate Phase C approval.

Reviewed: 2026-10-26 — complete test diff and supporting documentation
diffs reviewed in the conversation; no blocking issue found.
At this historical review checkpoint, PR validation, integration, and
commit recording were pending. See the integration reconciliation below.

### Integration and readiness reconciliation — 2026-11-01

B6 characterization merged through [PR #11](https://github.com/apeaircreative/my-final-assignment/pull/11) on
2026-10-26 at `638f565693ce3740855878033d8fd6183d803760`.
This supersedes the integration-pending status of the historical local
checkpoint above. It does not claim new tests, real-provider cancellation,
or a B6 production correction.

Partial offline evaluation tooling merged through [PR #18](https://github.com/apeaircreative/my-final-assignment/pull/18)
at `fbbc5547fdc53e3853f54c4949952b67607c4b2c`, with
[review reconciliation](https://github.com/apeaircreative/my-final-assignment/pull/18#issuecomment-6559504240) and
[owner acceptance](https://github.com/apeaircreative/my-final-assignment/pull/18#issuecomment-6559576782) recorded.
The acceptance is not independent second-person approval.

[Issue #12's assessment](https://github.com/apeaircreative/my-final-assignment/issues/12#issuecomment-6559721999)
is complete with a not-ready / execution-blocked outcome. Closure does
not establish verified execution readiness.

Remaining gates are retained under
[#14](https://github.com/apeaircreative/my-final-assignment/issues/14#issuecomment-6559721538) and
[#15](https://github.com/apeaircreative/my-final-assignment/issues/15#issuecomment-6559721747): verified real-provider
completion/stop, hard aggregate enforcement, an approved complete execution
path with truthful whole-run outcomes, and exact future-candidate
compatibility. [#13](https://github.com/apeaircreative/my-final-assignment/issues/13) remains the fresh-case prerequisite.
Issue #15's incomplete description also requires reconciliation before
execution.

Production B5 trace fidelity and explicit run-lifecycle implementation remain
separate proposals requiring scope approval, not additional implementation
requirements for the accepted partial checkpoint.

No candidate is frozen and live evaluation remains unauthorized.
This documentation reconciliation claims no new verification execution.

## Phase C — Demonstrated violations only

For each failed accepted-requirement test:

1. State the violated rule.
2. Explain the smallest compatible correction.
3. Obtain approval for the implementation change.
4. Apply the correction without unrelated refactoring.
5. Run the focused regression and full offline suite.
6. Review traces and output shape where relevant.
7. Update verification status and remaining limitations.
8. Review before committing.

Do not change the pinned course dependency, public interfaces, or architecture
as an incidental fix.

## Subsequent answer-quality evaluation

Only after the relevant correctness work:

- Freeze the candidate change and evaluation protocol.
- Keep model/runtime and requested sampling settings explicit.
- Define adoption and regression criteria before viewing results.
- Separate provider failures, mechanical rubric failures, and source-support
  review.
- Use newly authored, independently reviewed cases where required.
- Treat previously reviewed sets as consumed.
- Preserve answers, retrieved evidence, traces, and provenance.

A passing offline suite is not evidence of improved live-model answer quality.

## Per-task outcome record

Copy this section under each completed task.

### Outcome

Status: [passed / violation demonstrated / fixed and verified / blocked]

Tested revision or working-tree description:
[actual revision and relevant uncommitted changes]

Commands and actual outcomes:

- Focused test: [command and result]
- Full offline suite: [command and result]
- Diff check: [command and result]

Changed files:

- [actual file]

Evidence or limitation:

[what the result proves and does not prove]

Reviewed:
[date and decision]

Commit:
[actual SHA when available; otherwise pending]

## Evidence retention

Keep concise offline verification outcomes in this plan.

Keep executable assertions in tests/.

Keep existing model-experiment artifacts in runs/ unchanged.

Do not copy every successful terminal transcript into the repository.
Retain a longer transcript only when needed to explain a failure or
non-obvious verification result.
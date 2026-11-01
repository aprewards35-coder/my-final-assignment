# Offline evaluation controls — scope and limitations

## Status

Partial tooling checkpoint for issue #12.
Not evaluation-ready. Live evaluation remains unauthorized.

Reviewed implementation and test checkpoint:
9fa2c19124f300fb4c81b1e16c841692d894f883.

The tooling branch is based on:
f21c5a64fa29bcf5410955038cc5ff1cd24810b8.

## Purpose and ownership

scripts/evaluation_controls.py provides external evidence recording and
admission controls around an explicitly supplied application and client.

It does not provide a live-provider entry point, a quality evaluator,
a complete two-revision execution runner, or provider cancellation.

Application behavior, prompts, retrieval, corpus, and pinned dependencies
were not changed by these tooling checkpoints.

## Evidence recorded

- Configured admission limits and controlled-offline mode.
- Observed checkout provenance and allowlisted source fingerprints.
- Case starts, returned results, and construction/execution exceptions.
- Initial and repair client invocations, responses, and exceptions.
- Once-only admission-stop evidence.

Record timestamps and writer elapsed time are distinct from the attempt
gate's aggregate admission-budget origin.

Source fingerprints are collected sequentially, not as an atomic snapshot.
Installed dependency contents are not independently verified.

The writer limits each encoded record to 1 MiB. This is not a total
run-storage limit or a peak-memory bound during serialization.

## Interpreting outcomes

case_returned means one application invocation returned. It does not
establish whole-run completion or answer quality.

case_returned.data.provider_failure means the application trace reported
a provider-call failure at case return, including an application-level
timeout. It does not establish that the underlying client raised an
exception or that provider work terminated. Read it alongside
unresolved_invocation and subsequent client-call events.

case_raised means case construction or execution raised an exception.
It does not establish completed cleanup.

run_admission_stopped records stopped admission and the active attempt
at that point. It does not establish termination of existing provider work.

An unresolved attempt is an unresolved reservation, not proof that a
provider operation is currently running. A reservation can remain active
when start or terminal evidence cannot be persisted, including when the
underlying client was never called or has already returned.

A later client return or exception is subsequent evidence about that client
invocation. It does not retroactively change the earlier unresolved snapshot
or independently prove server-side termination.

The module has no explicit whole-run finalization interface. Consumers
must not infer successful run completion from a returned case, stopped
admission, or a closed evidence file.

Missing or incomplete terminal evidence must not be treated as successful
completion.

A concurrent rejected run_case() call stops admission but does not itself
write a separate rejection record; the active case can subsequently
record the stopped state.

## Executed controlled compatibility

Application snapshots tested:

- Selected baseline:
  da5776412fe0c200201032726b7db4a2f0cce954.
- Application checkpoint:
  6bb61668cd17da6f1cf7b9ad439ffce90701b271.

Each snapshot includes its own agent.py, safety.py, and tracked corpus.
Separate Python subprocesses isolate application imports.

The controls are imported from the working checkout. The existing installed
course dependency is shared. This is not a fully frozen evaluation
environment.

Three scenarios passed for each revision:

1. A schema-valid, human-review-requested response, comparing direct and
   recorded application results and client inputs.
2. Malformed initial output followed by repair failure, retaining both
   attempts despite the application's replacement failure trace and
   blocking further case admission.
3. Application timeout with unresolved controlled work, blocked subsequent
   dispatch, late completion evidence, and explicit worker release and join
   before closing the evidence writer.

The baseline's historical prompt formatting is preserved.

The application checkpoint is a compatibility target, not an approved
frozen evaluation candidate.

These scenarios do not establish supported cited-answer behavior, answer
quality, or compatibility with a future frozen candidate.

## Recorded verification

Before commit 9fa2c19124f300fb4c81b1e16c841692d894f883:

- Focused compatibility checks: 6 passed in 1.05s.
- Full offline suite: 161 passed in 4.98s.
- Repository Ruff: passed.
- Temporary-index and staged whitespace checks: passed.

Commands used:

    env BOOTCAMP_PROVIDER=fake \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
      .venv/bin/python -m pytest -p no:cacheprovider -v \
      tests/test_evaluation_revision_compatibility.py

    env BOOTCAMP_PROVIDER=fake \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
      .venv/bin/python -m pytest -p no:cacheprovider

    .venv/bin/ruff check .

These are historical local results, not a new execution at a later
documentation commit. No independent reviewer execution is claimed.

## Final local offline verification — 2026-11-01

Executed with HEAD at:
9fa2c19124f300fb4c81b1e16c841692d894f883.

The implementation and test files were unchanged. This documentation file
was present as an untracked working-tree addition.

- Focused controls and compatibility: 95 passed in 1.79s.
- Full offline suite: 161 passed in 6.61s.
- Repository Ruff: passed.
- Documentation whitespace check using a temporary index: passed.

Focused command:

    env BOOTCAMP_PROVIDER=fake \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
      .venv/bin/python -m pytest -p no:cacheprovider \
      tests/test_evaluation_controls.py \
      tests/test_evaluation_revision_compatibility.py

The full-suite and Ruff commands were the same as those recorded above.

Source review was performed incrementally in the conversation across the
controls module and both test files. It identified the documented outcome,
reservation, record-size, provenance, and execution-enforcement limitations.
No additional blocking discrepancy was identified for the partial offline
scope. This is not an independent reviewer execution or approval for live
evaluation.

## Remaining readiness limitations

Admission checks prevent further admission after observed limits or failure.
They do not interrupt existing work or establish a hard resource ceiling
across setup, model startup, and live execution.

Real-provider operation completion or stop remains unverified and is an
explicit live-execution blocker.

The controlled timeout uses a shortened application timeout and explicit
test-worker release/join. It does not verify real-provider cancellation.

Incremental conversational source review and final local offline verification
are recorded above. Owner acceptance and focused PR review remain pending.

No live-provider calls or graders were run for these checkpoints.
No quality improvement or evaluation-readiness approval is claimed.

## Deferred backlog — explicit run lifecycle

Before enabling an execution runner, define how it reports intended-run
completion, early stopping, unresolved invocations, and incomplete evidence.

Any completion claim must distinguish local client-invocation status from
verified provider-work completion.

Before implementation, check existing tracking, define the lifecycle
requirements, propose the smallest change and tests, and obtain separate
scope approval.

Deferred proposal only. This is not an additional implementation
requirement for the current partial checkpoint and does not resolve the
real-provider completion/stop blocker.

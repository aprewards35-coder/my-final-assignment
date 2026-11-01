from __future__ import annotations

import json
import os
import stat
from dataclasses import FrozenInstanceError

import pytest

from scripts.evaluation_controls import (
    MAX_RECORD_BYTES,
    AdmissionError,
    AttemptGate,
    CaseController,
    EvaluationLimits,
    EvidenceError,
    EvidenceWriter,
    RecordingClient,
    record_offline_provenance,
)


def test_limits_default_to_approved_protocol() -> None:
    limits = EvaluationLimits()

    assert limits.max_cases == 40
    assert limits.max_attempts == 80
    assert limits.max_elapsed_s == 3600.0


def test_lower_limits_are_allowed() -> None:
    limits = EvaluationLimits(max_cases=2, max_attempts=3, max_elapsed_s=0.25)

    assert limits.max_cases == 2
    assert limits.max_attempts == 3
    assert limits.max_elapsed_s == 0.25


def test_integer_elapsed_limit_is_allowed() -> None:
    assert EvaluationLimits(max_elapsed_s=1).max_elapsed_s == 1


@pytest.mark.parametrize("field", ["max_cases", "max_attempts"])
@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", None])
def test_invalid_counts_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        EvaluationLimits(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [("max_cases", 41), ("max_attempts", 81)],
)
def test_counts_cannot_exceed_approved_protocol(field: str, value: int) -> None:
    with pytest.raises(ValueError, match=field):
        EvaluationLimits(**{field: value})


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        0,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
        3600.1,
        10**400,
        "1",
        None,
    ],
)
def test_invalid_elapsed_limits_are_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="max_elapsed_s"):
        EvaluationLimits(max_elapsed_s=value)


def test_limits_cannot_be_mutated_after_validation() -> None:
    limits = EvaluationLimits()

    with pytest.raises(FrozenInstanceError):
        limits.max_cases = 41


def test_writer_preserves_structured_data_without_event_injection(tmp_path) -> None:
    writer = EvidenceWriter(tmp_path)
    hostile = 'hello\n{"event":"passed","sequence":999}'
    try:
        assert writer.write("attempt_started", {"text": hostile, "event": "fake"}) == 1
        assert writer.write("attempt_returned", {"response": "ok"}) == 2
    finally:
        writer.close()

    lines = writer.path.read_text().splitlines()
    assert len(lines) == 2
    first, second = [json.loads(line) for line in lines]
    assert first["event"] == "attempt_started"
    assert first["sequence"] == 1
    assert first["data"] == {"text": hostile, "event": "fake"}
    assert second["sequence"] == 2
    assert first["run_id"] == writer.run_id


def test_writer_creates_unique_runs_without_overwriting(tmp_path) -> None:
    first = EvidenceWriter(tmp_path)
    second = EvidenceWriter(tmp_path)
    try:
        first.write("first", {})
        before = first.path.read_bytes()
        second.write("second", {})
        assert first.run_dir != second.run_dir
        assert first.path.read_bytes() == before
    finally:
        first.close()
        second.close()


def test_writer_rejects_repository_and_descendants(tmp_path) -> None:
    repository = tmp_path / "repository"
    child = repository / "reports"
    child.mkdir(parents=True)

    for parent in (repository, child):
        with pytest.raises(ValueError, match="outside"):
            EvidenceWriter(parent, repository_root=repository)

    assert list(child.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission assertion")
def test_writer_uses_private_permissions(tmp_path) -> None:
    writer = EvidenceWriter(tmp_path)
    try:
        assert stat.S_IMODE(writer.run_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(writer.path.stat().st_mode) == 0o600
    finally:
        writer.close()


@pytest.mark.parametrize("data", [{"value": float("nan")}, {"value": object()}])
def test_writer_serialization_failure_is_permanent(tmp_path, data) -> None:
    writer = EvidenceWriter(tmp_path)
    try:
        with pytest.raises(EvidenceError):
            writer.write("invalid", data)
        assert writer.failed
        with pytest.raises(EvidenceError):
            writer.write("later", {})
        assert writer.path.read_bytes() == b""
    finally:
        writer.close()


def test_writer_rejects_oversized_evidence_without_truncation(tmp_path) -> None:
    writer = EvidenceWriter(tmp_path)
    try:
        with pytest.raises(EvidenceError):
            writer.write("large", {"text": "x" * MAX_RECORD_BYTES})
        assert writer.failed
        assert writer.path.read_bytes() == b""
    finally:
        writer.close()


def test_writer_persistence_failure_stops_future_writes(tmp_path, monkeypatch) -> None:
    writer = EvidenceWriter(tmp_path)
    try:
        writer.write("preserved", {})
        before = writer.path.read_bytes()

        def fail(encoded):
            raise OSError("simulated storage failure with sensitive details")

        monkeypatch.setattr(writer, "_persist", fail)
        with pytest.raises(EvidenceError) as caught:
            writer.write("failed", {})
        assert "sensitive" not in str(caught.value)
        assert caught.value.__suppress_context__
        assert writer.failed
        with pytest.raises(EvidenceError):
            writer.write("later", {})
        assert writer.path.read_bytes() == before
    finally:
        writer.close()


def test_writer_close_is_idempotent_and_blocks_writes(tmp_path) -> None:
    writer = EvidenceWriter(tmp_path)
    writer.close()
    writer.close()

    with pytest.raises(EvidenceError):
        writer.write("too_late", {})


def test_writer_partial_failure_preserves_incomplete_evidence(tmp_path, monkeypatch) -> None:
    writer = EvidenceWriter(tmp_path)
    partial = b'{"incomplete":'
    try:
        writer.write("preserved", {})
        before = writer.path.read_bytes()

        def fail_after_partial_write(encoded):
            writer._stream.write(partial)
            writer._stream.flush()
            raise OSError("simulated partial write")

        monkeypatch.setattr(writer, "_persist", fail_after_partial_write)
        with pytest.raises(EvidenceError):
            writer.write("interrupted_record", {})
        assert writer.failed
        with pytest.raises(EvidenceError):
            writer.write("later", {})
    finally:
        writer.close()

    assert writer.path.read_bytes() == before + partial
    assert not writer.path.read_bytes().endswith(b"\n")
    first, tail = writer.path.read_bytes().splitlines()
    assert json.loads(first)["event"] == "preserved"
    with pytest.raises(json.JSONDecodeError):
        json.loads(tail)


def test_writer_interruption_propagates_and_disables_writer(tmp_path, monkeypatch) -> None:
    writer = EvidenceWriter(tmp_path)
    interruption = KeyboardInterrupt()
    try:
        def interrupt(encoded):
            raise interruption

        monkeypatch.setattr(writer, "_persist", interrupt)
        with pytest.raises(KeyboardInterrupt) as caught:
            writer.write("interrupted", {})
        assert caught.value is interruption
        assert writer.failed
        with pytest.raises(EvidenceError):
            writer.write("later", {})
    finally:
        writer.close()


def test_writer_concurrent_writes_have_ordered_unique_records(tmp_path) -> None:
    import threading

    writer = EvidenceWriter(tmp_path)
    start = threading.Event()
    errors = []
    results = []
    result_lock = threading.Lock()

    def write_one(number):
        try:
            if not start.wait(2.0):
                raise RuntimeError("Controlled start signal was not observed")
            sequence = writer.write("concurrent", {"number": number})
            with result_lock:
                results.append(sequence)
        except BaseException as error:
            with result_lock:
                errors.append(error)

    workers = [threading.Thread(target=write_one, args=(i,), daemon=True) for i in range(8)]
    started = []
    try:
        for worker in workers:
            worker.start()
            started.append(worker)
        start.set()
        for worker in started:
            worker.join(2.0)
        assert all(not worker.is_alive() for worker in started)
        assert not errors
        assert sorted(results) == list(range(1, 9))
    finally:
        start.set()
        for worker in started:
            worker.join(2.0)
        if all(not worker.is_alive() for worker in started):
            writer.close()

    records = [json.loads(line) for line in writer.path.read_bytes().splitlines()]
    assert [record["sequence"] for record in records] == list(range(1, 9))
    assert {record["data"]["number"] for record in records} == set(range(8))


def test_writer_fsync_failure_disables_writer(tmp_path, monkeypatch) -> None:
    writer = EvidenceWriter(tmp_path)
    try:
        def fail_fsync(descriptor):
            raise OSError("simulated fsync failure")

        monkeypatch.setattr("scripts.evaluation_controls.os.fsync", fail_fsync)
        with pytest.raises(EvidenceError):
            writer.write("not_confirmed_persisted", {})
        assert writer.failed
        with pytest.raises(EvidenceError):
            writer.write("later", {})
    finally:
        writer.close()

    # Bytes may exist despite failed persistence confirmation.
    # Their presence must not make this writer usable again.
    assert writer.failed


def test_gate_no_calls_consume_no_attempts() -> None:
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)

    assert gate.reserved == 0
    assert gate.active is None
    assert not gate.stopped


def test_gate_counts_initial_and_repair_reservations() -> None:
    gate = AttemptGate(EvaluationLimits(max_attempts=2), clock=lambda: 0.0)

    first = gate.reserve()
    gate.finish(first)
    second = gate.reserve()
    gate.finish(second)

    assert (first, second) == (1, 2)
    assert gate.reserved == 2
    with pytest.raises(AdmissionError, match="Attempt budget"):
        gate.reserve()
    assert gate.stopped


@pytest.mark.parametrize("now", [1.0, 1.1])
def test_gate_blocks_at_or_after_deadline(now) -> None:
    readings = iter([0.0, now])
    gate = AttemptGate(EvaluationLimits(max_elapsed_s=1), clock=lambda: next(readings))

    with pytest.raises(AdmissionError, match="Elapsed-time"):
        gate.reserve()
    assert gate.reserved == 0
    assert gate.stopped


def test_gate_stop_allows_active_completion_but_never_reopens() -> None:
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    attempt = gate.reserve()

    gate.stop()
    assert gate.active == attempt
    gate.finish(attempt)

    assert gate.active is None
    assert gate.stopped
    with pytest.raises(AdmissionError, match="stopped"):
        gate.reserve()


def test_gate_overlap_stops_admission_without_losing_active_attempt() -> None:
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    attempt = gate.reserve()

    with pytest.raises(AdmissionError, match="already active"):
        gate.reserve()
    assert gate.reserved == 1
    assert gate.active == attempt
    assert gate.stopped
    gate.finish(attempt)


@pytest.mark.parametrize("bad_clock", [float("nan"), float("inf"), True, "0", -1.0])
def test_gate_invalid_or_backwards_clock_stops_admission(bad_clock) -> None:
    readings = iter([0.0, bad_clock])
    gate = AttemptGate(EvaluationLimits(), clock=lambda: next(readings))

    with pytest.raises(AdmissionError, match="Clock"):
        gate.reserve()
    assert gate.stopped
    assert gate.reserved == 0


def test_gate_wrong_completion_preserves_active_attempt_and_stops() -> None:
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    attempt = gate.reserve()

    with pytest.raises(AdmissionError, match="does not match"):
        gate.finish(attempt + 1)
    assert gate.active == attempt
    assert gate.stopped
    gate.finish(attempt)


def test_gate_clock_exception_stops_admission() -> None:
    readings = iter([0.0])

    def clock():
        return next(readings)

    gate = AttemptGate(EvaluationLimits(), clock=clock)
    with pytest.raises(AdmissionError, match="Clock"):
        gate.reserve()
    assert gate.stopped


TEST_REVISION = "f21c5a64fa29bcf5410955038cc5ff1cd24810b8"


class LocalClient:
    def __init__(self, error=None):
        self.calls = []
        self.error = error
        self.response = "unchanged response"

    def complete(self, system, user):
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        return self.response


def make_recording_client(tmp_path, client, *, clock=lambda: 0.0):
    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(max_attempts=2), clock=clock)
    recording = RecordingClient(
        client, gate, writer, case_id="controlled-case", revision=TEST_REVISION
    )
    return recording, gate, writer


def read_records(writer):
    return [json.loads(line) for line in writer.path.read_bytes().splitlines()]


def test_recording_forwards_unchanged_and_records_two_calls(tmp_path) -> None:
    underlying = LocalClient()
    client, gate, writer = make_recording_client(tmp_path, underlying)
    try:
        assert client.complete("system", "initial") is underlying.response
        assert client.complete("system", "repair") is underlying.response
        with pytest.raises(AdmissionError):
            client.complete("system", "extra")
        assert underlying.calls == [("system", "initial"), ("system", "repair")]
        records = read_records(writer)
        assert [row["event"] for row in records] == [
            "attempt_started", "client_call_returned",
            "attempt_started", "client_call_returned",
        ]
        assert [row["data"]["attempt_id"] for row in records] == [1, 1, 2, 2]
        assert all(row["data"]["revision"] == TEST_REVISION for row in records)
        assert gate.reserved == 2
    finally:
        writer.close()


@pytest.mark.parametrize("error", [ConnectionError("secret"), RuntimeError("secret")])
def test_recording_preserves_exception_and_stops(tmp_path, error) -> None:
    underlying = LocalClient(error)
    client, gate, writer = make_recording_client(tmp_path, underlying)
    try:
        with pytest.raises(type(error)) as caught:
            client.complete("system", "question")
        assert caught.value is error
        assert gate.stopped
        assert gate.active is None
        with pytest.raises(AdmissionError):
            client.complete("system", "later")
        records = read_records(writer)
        assert records[-1]["event"] == "client_call_raised"
        assert records[-1]["data"]["exception_type"] == type(error).__name__
        assert "secret" not in writer.path.read_text()
        assert len(underlying.calls) == 1
    finally:
        writer.close()


def test_recording_start_write_failure_never_calls_client(tmp_path, monkeypatch) -> None:
    underlying = LocalClient()
    client, gate, writer = make_recording_client(tmp_path, underlying)
    try:
        def fail(encoded):
            raise OSError("controlled failure")

        monkeypatch.setattr(writer, "_persist", fail)
        with pytest.raises(EvidenceError):
            client.complete("system", "question")
        assert underlying.calls == []
        assert gate.reserved == 1
        assert gate.active == 1
        assert gate.stopped
    finally:
        writer.close()


def test_recording_terminal_write_failure_leaves_unresolved_attempt(tmp_path, monkeypatch) -> None:
    underlying = LocalClient()
    client, gate, writer = make_recording_client(tmp_path, underlying)
    persist = writer._persist
    writes = []

    def fail_second(encoded):
        writes.append(encoded)
        if len(writes) == 2:
            raise OSError("controlled terminal failure")
        persist(encoded)

    try:
        monkeypatch.setattr(writer, "_persist", fail_second)
        with pytest.raises(EvidenceError):
            client.complete("system", "question")
        assert len(underlying.calls) == 1
        assert gate.active == 1
        assert gate.stopped
        assert [row["event"] for row in read_records(writer)] == ["attempt_started"]
    finally:
        writer.close()


def test_recording_rechecks_deadline_after_start_persistence(tmp_path) -> None:
    readings = iter([0.0, 0.0, 3600.0])
    underlying = LocalClient()
    client, gate, writer = make_recording_client(
        tmp_path, underlying, clock=lambda: next(readings)
    )
    try:
        with pytest.raises(AdmissionError, match="Elapsed-time"):
            client.complete("system", "question")
        assert underlying.calls == []
        assert gate.reserved == 1
        assert gate.active is None
        assert gate.stopped
        assert [row["event"] for row in read_records(writer)] == [
            "attempt_started", "attempt_not_dispatched"
        ]
    finally:
        writer.close()


def test_recording_late_response_does_not_reopen_stopped_gate(tmp_path) -> None:
    import threading

    started = threading.Event()
    release = threading.Event()
    outcome = {}

    class ControlledClient:
        def complete(self, system, user):
            started.set()
            if not release.wait(2.0):
                raise RuntimeError("Controlled release not observed")
            return "late response"

    client, gate, writer = make_recording_client(tmp_path, ControlledClient())

    def invoke():
        try:
            outcome["response"] = client.complete("system", "question")
        except BaseException as error:
            outcome["error"] = error

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    try:
        assert started.wait(1.0)
        gate.stop()
        assert gate.active == 1
        release.set()
        worker.join(2.0)
        assert not worker.is_alive()
        assert outcome == {"response": "late response"}
        assert gate.active is None
        assert gate.stopped
        assert read_records(writer)[-1]["event"] == "client_call_returned"
        with pytest.raises(AdmissionError):
            client.complete("system", "later")
    finally:
        release.set()
        worker.join(2.0)
        if not worker.is_alive():
            writer.close()


def test_recording_preserves_actual_application_repair_failure(tmp_path) -> None:
    from agent import YourAgent

    class RepairFailureClient:
        def __init__(self):
            self.calls = []

        def complete(self, system, user):
            self.calls.append((system, user))
            if len(self.calls) == 1:
                return "{not valid JSON"
            if len(self.calls) == 2:
                raise ConnectionError("controlled repair failure")
            raise AssertionError("Unexpected third invocation")

    underlying = RepairFailureClient()
    client, gate, writer = make_recording_client(tmp_path, underlying)
    try:
        result = YourAgent(client=client).run("How does chunking work in RAG?")

        assert len(underlying.calls) == 2
        assert result.answer.needs_human_review
        assert result.answer.citations == ()
        assert result.answer.confidence == 0.0
        assert gate.stopped
        assert gate.active is None

        records = read_records(writer)
        assert [row["event"] for row in records] == [
            "attempt_started",
            "client_call_returned",
            "attempt_started",
            "client_call_raised",
        ]
        assert records[1]["data"]["response"] == "{not valid JSON"
        assert records[3]["data"]["exception_type"] == "ConnectionError"
        assert records[2]["data"]["system"] == records[0]["data"]["system"]
        assert records[2]["data"]["user"] == (
            records[0]["data"]["user"]
            + "\n\nYour previous reply was not valid. Return ONLY the JSON object."
        )
        assert underlying.calls == [
            (records[0]["data"]["system"], records[0]["data"]["user"]),
            (records[2]["data"]["system"], records[2]["data"]["user"]),
        ]

        # The application still has its original B5 replacement trace.
        # External recording must not silently fix application behavior.
        assert [event.kind for event in result.trace] == [
            "retrieve", "llm_call", "decision"
        ]
        assert result.trace[1].detail == "provider call failed: ConnectionError"
    finally:
        writer.close()


def test_recording_stop_during_start_write_prevents_forwarding(tmp_path, monkeypatch) -> None:
    underlying = LocalClient()
    client, gate, writer = make_recording_client(tmp_path, underlying)
    persist = writer._persist

    def persist_then_stop(encoded):
        persist(encoded)
        gate.stop()

    try:
        monkeypatch.setattr(writer, "_persist", persist_then_stop)
        with pytest.raises(AdmissionError):
            client.complete("system", "question")
        assert underlying.calls == []
        assert gate.stopped
        assert gate.active is None
        assert gate.reserved == 1
        assert [row["event"] for row in read_records(writer)] == [
            "attempt_started", "attempt_not_dispatched"
        ]
    finally:
        writer.close()


def test_recording_exception_evidence_failure_remains_unresolved(tmp_path, monkeypatch) -> None:
    underlying = LocalClient(ConnectionError("private error details"))
    client, gate, writer = make_recording_client(tmp_path, underlying)
    persist = writer._persist
    writes = []

    def fail_second(encoded):
        writes.append(encoded)
        if len(writes) == 2:
            raise OSError("controlled evidence failure")
        persist(encoded)

    try:
        monkeypatch.setattr(writer, "_persist", fail_second)
        with pytest.raises(EvidenceError):
            client.complete("system", "question")
        assert len(underlying.calls) == 1
        assert gate.stopped
        assert gate.active == 1
        assert writer.failed
        assert [row["event"] for row in read_records(writer)] == ["attempt_started"]
        assert "private error details" not in writer.path.read_text()
        with pytest.raises(AdmissionError):
            client.complete("system", "later")
    finally:
        writer.close()


def test_recording_actual_application_timeout_preserves_late_completion(tmp_path) -> None:
    import threading

    from agent import YourAgent

    started = threading.Event()
    release = threading.Event()
    invocation_finished = threading.Event()
    original_invocation = {}
    outcome = {}

    class ControlledClient:
        def complete(self, system, user):
            original_invocation["thread"] = threading.current_thread()
            started.set()
            if not release.wait(5.0):
                raise RuntimeError("Controlled release was not observed")
            return '{"answer":"Late","citations":[],"confidence":0,"needs_human_review":true}'

    class SignallingRecordingClient(RecordingClient):
        def complete(self, system, user):
            try:
                return super().complete(system, user)
            finally:
                if threading.current_thread() is original_invocation.get("thread"):
                    invocation_finished.set()

    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    client = SignallingRecordingClient(
        ControlledClient(), gate, writer,
        case_id="controlled-timeout", revision=TEST_REVISION,
    )
    agent = YourAgent(client=client)
    agent.timeout_s = 0.05

    def invoke():
        try:
            outcome["result"] = agent.run("How does chunking work in RAG?")
        except BaseException as error:
            outcome["error"] = error

    caller = threading.Thread(target=invoke, daemon=True)
    caller.start()
    try:
        assert started.wait(1.0)
        caller.join(1.0)
        assert not caller.is_alive(), "Application caller did not return"
        assert "error" not in outcome
        result = outcome["result"]
        assert result.answer.needs_human_review
        assert result.answer.citations == ()
        assert result.answer.confidence == 0.0
        assert any(
            event.kind == "llm_call"
            and event.detail == "provider call failed: TimeoutError"
            for event in result.trace
        )

        assert gate.active == 1
        assert not invocation_finished.is_set()
        assert [row["event"] for row in read_records(writer)] == ["attempt_started"]

        # Manual stop for characterization; the controller does not exist yet.
        gate.stop()
        with pytest.raises(AdmissionError):
            client.complete("system", "must not dispatch")

        release.set()
        assert invocation_finished.wait(2.0)
        assert gate.active is None
        assert gate.stopped
        assert [row["event"] for row in read_records(writer)] == [
            "attempt_started", "client_call_returned"
        ]
        with pytest.raises(AdmissionError):
            client.complete("system", "must remain stopped")
    finally:
        release.set()
        caller.join(2.0)
        finished = invocation_finished.wait(2.0)
        if finished and not caller.is_alive():
            writer.close()


def test_recording_overlap_rejects_second_underlying_call(tmp_path) -> None:
    import threading

    started = threading.Event()
    release = threading.Event()
    calls = []
    outcome = {}

    class ControlledClient:
        def complete(self, system, user):
            calls.append((system, user))
            started.set()
            if not release.wait(5.0):
                raise RuntimeError("Controlled release was not observed")
            return "controlled response"

    client, gate, writer = make_recording_client(tmp_path, ControlledClient())

    def invoke():
        try:
            outcome["response"] = client.complete("system", "first")
        except BaseException as error:
            outcome["error"] = error

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    try:
        assert started.wait(1.0)
        with pytest.raises(AdmissionError, match="already active"):
            client.complete("system", "second")
        assert calls == [("system", "first")]
        assert gate.reserved == 1
        assert gate.stopped

        release.set()
        worker.join(2.0)
        assert not worker.is_alive()
        assert outcome == {"response": "controlled response"}
        assert gate.active is None
        assert gate.stopped
        assert [row["event"] for row in read_records(writer)] == [
            "attempt_started", "client_call_returned"
        ]
    finally:
        release.set()
        worker.join(2.0)
        if not worker.is_alive():
            writer.close()


def test_controller_stops_after_provider_failure(tmp_path) -> None:
    from agent import YourAgent

    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    controller = CaseController(gate, writer)
    underlying = LocalClient(ConnectionError("controlled failure"))
    try:
        result = controller.run_case(
            case_id="first", revision=TEST_REVISION,
            question="How does chunking work in RAG?",
            client=underlying, agent_factory=YourAgent,
        )
        assert result.answer.needs_human_review
        assert gate.stopped
        assert controller.cases_admitted == 1
        with pytest.raises(AdmissionError):
            controller.run_case(
                case_id="second", revision=TEST_REVISION,
                question="How does chunking work in RAG?",
                client=underlying, agent_factory=YourAgent,
            )
        assert len(underlying.calls) == 1
        terminal = next(
            row for row in read_records(writer) if row["event"] == "case_returned"
        )
        assert terminal["event"] == "case_returned"
        assert terminal["data"]["provider_failure"]
        assert terminal["data"]["admission_stopped"]
    finally:
        writer.close()


def test_controller_zero_call_cases_obey_case_cap(tmp_path) -> None:
    from bootcamp_agent.agent import AgentResult, _refusal

    class ZeroCallAgent:
        def __init__(self, *, client):
            self.client = client

        def run(self, question):
            return AgentResult(answer=_refusal(), trace=())

    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(max_cases=1), clock=lambda: 0.0)
    controller = CaseController(gate, writer)
    underlying = LocalClient()
    try:
        controller.run_case(
            case_id="first", revision=TEST_REVISION, question="controlled",
            client=underlying, agent_factory=ZeroCallAgent,
        )
        assert gate.reserved == 0
        assert underlying.calls == []
        with pytest.raises(AdmissionError, match="Case budget"):
            controller.run_case(
                case_id="second", revision=TEST_REVISION, question="controlled",
                client=underlying, agent_factory=ZeroCallAgent,
            )
        assert controller.cases_admitted == 1
        assert gate.stopped
    finally:
        writer.close()


def test_controller_rejects_repeat_without_second_execution(tmp_path) -> None:
    from bootcamp_agent.agent import AgentResult, _refusal

    calls = []

    class ZeroCallAgent:
        def __init__(self, *, client):
            pass

        def run(self, question):
            calls.append(question)
            return AgentResult(answer=_refusal(), trace=())

    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    controller = CaseController(gate, writer)
    arguments = {
        "case_id": "same", "revision": TEST_REVISION, "question": "controlled",
        "client": LocalClient(), "agent_factory": ZeroCallAgent,
    }
    try:
        controller.run_case(**arguments)
        with pytest.raises(AdmissionError, match="repeats"):
            controller.run_case(**arguments)
        assert calls == ["controlled"]
        assert controller.cases_admitted == 1
        assert gate.stopped
    finally:
        writer.close()


def test_controller_start_evidence_failure_prevents_agent_construction(
    tmp_path, monkeypatch
) -> None:
    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    controller = CaseController(gate, writer)
    constructed = []

    def factory(*, client):
        constructed.append(client)
        raise AssertionError("Factory must not run")

    def fail(encoded):
        raise OSError("controlled failure")

    try:
        monkeypatch.setattr(writer, "_persist", fail)
        with pytest.raises(EvidenceError):
            controller.run_case(
                case_id="first", revision=TEST_REVISION, question="controlled",
                client=LocalClient(), agent_factory=factory,
            )
        assert constructed == []
        assert gate.reserved == 0
        assert gate.stopped
        assert writer.failed
    finally:
        writer.close()


def test_controller_automatically_stops_after_application_timeout(tmp_path) -> None:
    import threading

    from agent import YourAgent

    started = threading.Event()
    release = threading.Event()
    provider_thread = {}
    outcome = {}
    calls = []

    class ControlledClient:
        def complete(self, system, user):
            provider_thread["thread"] = threading.current_thread()
            calls.append((system, user))
            started.set()
            if not release.wait(5.0):
                raise RuntimeError("Controlled release was not observed")
            return '{"answer":"Late","citations":[],"confidence":0,"needs_human_review":true}'

    def factory(*, client):
        agent = YourAgent(client=client)
        agent.timeout_s = 0.05
        return agent

    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    controller = CaseController(gate, writer)
    underlying = ControlledClient()

    def invoke():
        try:
            outcome["result"] = controller.run_case(
                case_id="timeout", revision=TEST_REVISION,
                question="How does chunking work in RAG?",
                client=underlying, agent_factory=factory,
            )
        except BaseException as error:
            outcome["error"] = error

    caller = threading.Thread(target=invoke, daemon=True)
    caller.start()
    try:
        assert started.wait(1.0)
        caller.join(1.0)
        assert not caller.is_alive()
        assert "error" not in outcome
        assert outcome["result"].answer.needs_human_review

        # No manual gate.stop(): the controller must make this decision.
        assert gate.stopped
        assert gate.active == 1
        terminal = next(
            row for row in read_records(writer) if row["event"] == "case_returned"
        )
        assert terminal["event"] == "case_returned"
        assert terminal["data"]["provider_failure"]
        assert terminal["data"]["unresolved_invocation"]
        assert terminal["data"]["admission_stopped"]

        with pytest.raises(AdmissionError):
            controller.run_case(
                case_id="must-not-run", revision=TEST_REVISION,
                question="How does chunking work in RAG?",
                client=underlying, agent_factory=factory,
            )
        assert controller.cases_admitted == 1
        assert len(calls) == 1

        release.set()
        provider_thread["thread"].join(2.0)
        assert not provider_thread["thread"].is_alive()
        assert gate.active is None
        assert gate.stopped

        records = read_records(writer)
        assert records[-1]["event"] == "client_call_returned"
        timeout_record = next(
            row for row in records if row["event"] == "case_returned"
        )
        assert timeout_record["data"]["unresolved_invocation"]
        assert timeout_record["sequence"] < records[-1]["sequence"]
    finally:
        release.set()
        caller.join(2.0)
        worker = provider_thread.get("thread")
        if worker is not None:
            worker.join(2.0)
        if not caller.is_alive() and (worker is None or not worker.is_alive()):
            writer.close()


def test_controller_factory_exception_stops_admission(tmp_path) -> None:
    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    controller = CaseController(gate, writer)
    error = RuntimeError("controlled construction failure")

    def factory(*, client):
        raise error

    try:
        with pytest.raises(RuntimeError) as caught:
            controller.run_case(
                case_id="factory-failure", revision=TEST_REVISION,
                question="controlled", client=LocalClient(), agent_factory=factory,
            )
        assert caught.value is error
        assert gate.stopped
        assert gate.reserved == 0
        assert controller.cases_admitted == 1
        records = read_records(writer)
        assert [row["event"] for row in records] == [
            "offline_provenance", "run_started", "case_started",
            "case_raised", "run_admission_stopped",
        ]
        assert records[-2]["data"]["phase"] == "agent_construction"
        assert records[-2]["data"]["exception_type"] == "RuntimeError"
    finally:
        writer.close()


def test_controller_deadline_during_start_write_blocks_factory(tmp_path, monkeypatch) -> None:
    now = [0.0]
    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(
        EvaluationLimits(max_elapsed_s=1), clock=lambda: now[0]
    )
    controller = CaseController(gate, writer)
    constructed = []
    persist = writer._persist

    def persist_then_expire(encoded):
        persist(encoded)
        now[0] = 1.0

    def factory(*, client):
        constructed.append(client)
        raise AssertionError("Factory must not run")

    try:
        monkeypatch.setattr(writer, "_persist", persist_then_expire)
        with pytest.raises(AdmissionError, match="Elapsed-time"):
            controller.run_case(
                case_id="expired", revision=TEST_REVISION,
                question="controlled", client=LocalClient(), agent_factory=factory,
            )
        assert constructed == []
        assert gate.stopped
        assert gate.reserved == 0
        assert controller.cases_admitted == 1
        records = read_records(writer)
        assert [row["event"] for row in records] == [
            "offline_provenance", "run_started", "case_started",
            "case_raised", "run_admission_stopped",
        ]
        assert records[-2]["data"]["phase"] == "pre_construction_admission"
        assert records[-2]["data"]["exception_type"] == "AdmissionError"
    finally:
        writer.close()


def test_writer_records_utc_and_monotonic_elapsed_time(tmp_path) -> None:
    from datetime import datetime

    readings = iter([100.0, 100.25, 101.0])
    writer = EvidenceWriter(tmp_path, clock=lambda: next(readings))
    try:
        writer.write("first", {})
        writer.write("second", {})
    finally:
        writer.close()

    records = read_records(writer)
    assert [row["writer_elapsed_s"] for row in records] == [0.25, 1.0]
    for row in records:
        timestamp = datetime.fromisoformat(row["recorded_at_utc"])
        assert timestamp.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("bad_clock", [float("nan"), float("inf"), True, "0", 99.0])
def test_writer_bad_event_clock_permanently_disables_recording(tmp_path, bad_clock) -> None:
    readings = iter([100.0, bad_clock])
    writer = EvidenceWriter(tmp_path, clock=lambda: next(readings))
    try:
        with pytest.raises(EvidenceError):
            writer.write("invalid_clock", {})
        assert writer.failed
        with pytest.raises(EvidenceError):
            writer.write("later", {})
        assert writer.path.read_bytes() == b""
    finally:
        writer.close()


def test_writer_clock_exception_permanently_disables_recording(tmp_path) -> None:
    readings = iter([100.0])
    writer = EvidenceWriter(tmp_path, clock=lambda: next(readings))
    try:
        with pytest.raises(EvidenceError):
            writer.write("clock_exhausted", {})
        assert writer.failed
    finally:
        writer.close()


def test_writer_invalid_initial_clock_creates_no_run_directory(tmp_path) -> None:
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError, match="Clock"):
        EvidenceWriter(tmp_path, clock=lambda: float("nan"))
    assert set(tmp_path.iterdir()) == before


def test_offline_provenance_records_observed_sources_not_candidate_approval(tmp_path) -> None:
    writer = EvidenceWriter(tmp_path)
    try:
        record_offline_provenance(writer)
        records = read_records(writer)
        assert len(records) == 1
        assert records[0]["event"] == "offline_provenance"
        data = records[0]["data"]
        assert data["selected_baseline"] == (
            "da5776412fe0c200201032726b7db4a2f0cce954"
        )
        assert len(data["observed_head"]) == 40
        assert isinstance(data["working_tree_dirty"], bool)
        assert data["candidate_revision"] is None
        assert data["live_execution_authorized"] is False
        assert data["baseline_execution_verified"] is False
        assert data["snapshot_atomic"] is False
        assert data["installed_dependency_contents_verified"] is False

        hashes = data["source_sha256"]
        assert "scripts/evaluation_controls.py" in hashes
        assert "agent.py" in hashes
        assert all(
            name in {
                "scripts/evaluation_controls.py",
                "agent.py", "safety.py", "pyproject.toml", "uv.lock",
            } or name.startswith("data/corpus/")
            for name in hashes
        )
        assert all(len(value) == 64 for value in hashes.values())
        assert ".env" not in hashes
    finally:
        writer.close()


def test_offline_provenance_git_failure_records_no_success(tmp_path, monkeypatch) -> None:
    writer = EvidenceWriter(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("private diagnostic details")

    try:
        monkeypatch.setattr(
            "scripts.evaluation_controls.subprocess.check_output", fail
        )
        with pytest.raises(EvidenceError) as caught:
            record_offline_provenance(writer)
        assert "private" not in str(caught.value)
        assert read_records(writer) == []
    finally:
        writer.close()


def test_controller_records_startup_before_any_case(tmp_path) -> None:
    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    try:
        controller = CaseController(gate, writer)
        records = read_records(writer)
        assert [row["event"] for row in records] == [
            "offline_provenance", "run_started"
        ]
        assert records[1]["data"]["max_attempts"] == 80
        assert records[1]["data"]["budget_origin"] == "attempt_gate_construction"
        assert records[1]["data"]["live_execution_authorized"] is False
        assert controller.cases_admitted == 0
        assert gate.reserved == 0
    finally:
        writer.close()


def test_controller_provenance_failure_stops_startup(tmp_path, monkeypatch) -> None:
    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)

    def fail(writer):
        raise EvidenceError("controlled provenance failure")

    try:
        monkeypatch.setattr(
            "scripts.evaluation_controls.record_offline_provenance", fail
        )
        with pytest.raises(EvidenceError):
            CaseController(gate, writer)
        assert gate.stopped
        assert gate.reserved == 0
        assert read_records(writer) == []
    finally:
        writer.close()


def test_controller_records_admission_stop_once_without_claiming_termination(tmp_path) -> None:
    from agent import YourAgent

    writer = EvidenceWriter(tmp_path)
    gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
    controller = CaseController(gate, writer)
    underlying = LocalClient(ConnectionError("controlled failure"))
    try:
        controller.run_case(
            case_id="first", revision=TEST_REVISION,
            question="How does chunking work in RAG?",
            client=underlying, agent_factory=YourAgent,
        )
        for case_id in ("second", "third"):
            with pytest.raises(AdmissionError):
                controller.run_case(
                    case_id=case_id, revision=TEST_REVISION,
                    question="controlled",
                    client=underlying, agent_factory=YourAgent,
                )
        stopped = [
            row for row in read_records(writer)
            if row["event"] == "run_admission_stopped"
        ]
        assert len(stopped) == 1
        assert stopped[0]["data"]["cases_admitted"] == 1
        assert stopped[0]["data"]["attempts_reserved"] == 1
        assert stopped[0]["data"]["provider_work_termination_verified"] is False
        assert len(underlying.calls) == 1
    finally:
        writer.close()

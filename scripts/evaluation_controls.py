"""Offline evaluation-control primitives.

This module does not construct providers or execute evaluations.
Validated limits are configuration, not enforcement or cancellation.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

APPROVED_MAX_CASES = 40
APPROVED_MAX_ATTEMPTS = 80
APPROVED_MAX_ELAPSED_S = 3600.0


def _validate_count(name: str, value: object, ceiling: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a positive integer")
    if not 1 <= value <= ceiling:
        raise ValueError(f"{name} must be between 1 and {ceiling}")


@dataclass(frozen=True)
class EvaluationLimits:
    """Limits bounded by the approved protocol; enforcement is separate."""

    max_cases: int = APPROVED_MAX_CASES
    max_attempts: int = APPROVED_MAX_ATTEMPTS
    max_elapsed_s: float = APPROVED_MAX_ELAPSED_S

    def __post_init__(self) -> None:
        _validate_count("max_cases", self.max_cases, APPROVED_MAX_CASES)
        _validate_count("max_attempts", self.max_attempts, APPROVED_MAX_ATTEMPTS)

        value = self.max_elapsed_s
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("max_elapsed_s must be a positive finite number")
        if not 0 < value <= APPROVED_MAX_ELAPSED_S or not math.isfinite(value):
            raise ValueError(
                f"max_elapsed_s must be finite and between 0 (exclusive) "
                f"and {APPROVED_MAX_ELAPSED_S}"
            )


MAX_RECORD_BYTES = 1024 * 1024
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class EvidenceError(RuntimeError):
    """Evidence cannot be recorded reliably; further admission must stop."""


class EvidenceWriter:
    """Append bounded JSONL records in a unique external run directory.

    Each successful write flushes and fsyncs the file. This is not a universal
    crash/power-loss guarantee, nor a promise of directory-entry durability.
    An interrupted final line is incomplete evidence, never proof of success.
    """

    def __init__(
        self,
        output_parent: Path,
        *,
        repository_root: Path = REPOSITORY_ROOT,
    ) -> None:
        parent = Path(output_parent).resolve(strict=True)
        repository = Path(repository_root).resolve(strict=True)
        if parent == repository or repository in parent.parents:
            raise ValueError("Evidence output must be outside the repository")
        if not parent.is_dir():
            raise ValueError("Evidence output parent must be a directory")

        self._lock = threading.Lock()
        self._failed = False
        self._closed = False
        self._sequence = 0
        self.run_dir = Path(tempfile.mkdtemp(prefix="evaluation-", dir=parent))
        self.run_id = self.run_dir.name
        self.path = self.run_dir / "events.jsonl"
        try:
            descriptor = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                self._stream = os.fdopen(descriptor, "wb")
            except BaseException:
                os.close(descriptor)
                raise
        except Exception:
            raise EvidenceError("Could not initialize evidence file") from None

    @property
    def failed(self) -> bool:
        with self._lock:
            return self._failed

    def _persist(self, encoded: bytes) -> None:
        written = self._stream.write(encoded)
        if written != len(encoded):
            raise OSError("Incomplete evidence write")
        self._stream.flush()
        os.fsync(self._stream.fileno())

    def write(self, event: str, data: dict) -> int:
        """Write trusted envelope fields around an untrusted data object."""
        with self._lock:
            if self._failed or self._closed:
                raise EvidenceError("Evidence writer is unavailable")
            try:
                if not isinstance(event, str) or not event:
                    raise ValueError("Event name must be nonempty text")
                if not isinstance(data, dict):
                    raise ValueError("Event data must be an object")
                sequence = self._sequence + 1
                record = {
                    "schema": "evaluation-evidence.v1",
                    "run_id": self.run_id,
                    "sequence": sequence,
                    "event": event,
                    "data": data,
                }
                encoded = (
                    json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n"
                ).encode("utf-8")
                if len(encoded) > MAX_RECORD_BYTES:
                    raise ValueError("Evidence record exceeds size limit")
                self._persist(encoded)
                self._sequence = sequence
                return sequence
            except BaseException as error:
                self._failed = True
                if not isinstance(error, Exception):
                    raise
                raise EvidenceError("Evidence record could not be persisted") from None

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._stream.close()
            except BaseException as error:
                self._failed = True
                if not isinstance(error, Exception):
                    raise
                raise EvidenceError("Evidence file could not be closed") from None


class AdmissionError(RuntimeError):
    """The harness refused admission; this is not a provider failure."""


class AttemptGate:
    """Thread-safe attempt reservations, not cancellation or case dispatch."""

    def __init__(self, limits: EvaluationLimits, *, clock=time.monotonic) -> None:
        self._limits = limits
        self._clock = clock
        self._lock = threading.Lock()
        self._started = self._read_clock()
        self._last = self._started
        self._reserved = 0
        self._active: int | None = None
        self._stopped = False

    def _read_clock(self) -> float:
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Clock must return a finite number")
        if not math.isfinite(value):
            raise ValueError("Clock must return a finite number")
        return value

    @property
    def reserved(self) -> int:
        with self._lock:
            return self._reserved

    @property
    def active(self) -> int | None:
        with self._lock:
            return self._active

    @property
    def stopped(self) -> bool:
        with self._lock:
            return self._stopped

    def stop(self) -> None:
        """Permanently stop admission without declaring active work complete."""
        with self._lock:
            self._stopped = True

    def reserve(self) -> int:
        with self._lock:
            if self._stopped:
                raise AdmissionError("Admission is stopped")
            if self._active is not None:
                self._stopped = True
                raise AdmissionError("An underlying call is already active")
            try:
                now = self._read_clock()
                if now < self._last:
                    raise ValueError("Clock moved backwards")
                self._last = now
            except BaseException as error:
                self._stopped = True
                if not isinstance(error, Exception):
                    raise
                raise AdmissionError("Clock observation failed") from None
            if now - self._started >= self._limits.max_elapsed_s:
                self._stopped = True
                raise AdmissionError("Elapsed-time budget exhausted")
            if self._reserved >= self._limits.max_attempts:
                self._stopped = True
                raise AdmissionError("Attempt budget exhausted")
            self._reserved += 1
            self._active = self._reserved
            return self._active

    def finish(self, attempt_id: int) -> None:
        """Clear the matching reservation; this proves no server-side outcome."""
        with self._lock:
            if (
                isinstance(attempt_id, bool)
                or not isinstance(attempt_id, int)
                or self._active is None
                or attempt_id != self._active
            ):
                self._stopped = True
                raise AdmissionError("Attempt completion does not match active reservation")
            self._active = None


    def check_dispatch(self, attempt_id: int) -> None:
        """Recheck admission after start-record persistence.

        This is an admission decision, not a hard real-time dispatch guarantee.
        No lock is held across the subsequent underlying call.
        """
        with self._lock:
            if self._stopped or self._active != attempt_id:
                self._stopped = True
                raise AdmissionError("Dispatch is stopped or reservation mismatched")
            try:
                now = self._read_clock()
                if now < self._last:
                    raise ValueError("Clock moved backwards")
                self._last = now
            except BaseException as error:
                self._stopped = True
                if not isinstance(error, Exception):
                    raise
                raise AdmissionError("Clock observation failed") from None
            if now - self._started >= self._limits.max_elapsed_s:
                self._stopped = True
                raise AdmissionError("Elapsed-time budget exhausted")


    @property
    def limits(self) -> EvaluationLimits:
        return self._limits

    def check_case_admission(self) -> None:
        """Check readiness without consuming a generation reservation."""
        with self._lock:
            if self._stopped:
                raise AdmissionError("Admission is stopped")
            if self._active is not None:
                self._stopped = True
                raise AdmissionError("Underlying work remains unresolved")
            try:
                now = self._read_clock()
                if now < self._last:
                    raise ValueError("Clock moved backwards")
                self._last = now
            except BaseException as error:
                self._stopped = True
                if not isinstance(error, Exception):
                    raise
                raise AdmissionError("Clock observation failed") from None
            if now - self._started >= self._limits.max_elapsed_s:
                self._stopped = True
                raise AdmissionError("Elapsed-time budget exhausted")
            if self._reserved >= self._limits.max_attempts:
                self._stopped = True
                raise AdmissionError("Attempt budget exhausted")


class RecordingClient:
    """Observe an explicitly supplied client; never construct a provider.

    Client return/exception events do not prove server-side completion.
    The controller must keep this writer open while an invocation is active.
    """

    def __init__(
        self,
        client,
        gate: AttemptGate,
        writer: EvidenceWriter,
        *,
        case_id: str,
        revision: str,
    ) -> None:
        if not isinstance(case_id, str) or not case_id or len(case_id) > 256:
            raise ValueError("case_id must be nonempty text of at most 256 characters")
        if (
            not isinstance(revision, str)
            or len(revision) != 40
            or any(character not in "0123456789abcdef" for character in revision)
        ):
            raise ValueError("revision must be an exact lowercase 40-character Git SHA")
        self._client = client
        self._gate = gate
        self._writer = writer
        self._case_id = case_id
        self._revision = revision

    def _write(self, event: str, data: dict) -> None:
        try:
            self._writer.write(event, data)
        except BaseException:
            self._gate.stop()
            raise

    def complete(self, system: str, user: str) -> str:
        attempt = self._gate.reserve()
        identity = {
            "attempt_id": attempt,
            "case_id": self._case_id,
            "revision": self._revision,
        }
        self._write(
            "attempt_started",
            {**identity, "system": system, "user": user},
        )
        try:
            self._gate.check_dispatch(attempt)
        except BaseException:
            self._gate.stop()
            self._write("attempt_not_dispatched", identity)
            self._gate.finish(attempt)
            raise

        try:
            response = self._client.complete(system=system, user=user)
        except BaseException as error:
            self._gate.stop()
            self._write(
                "client_call_raised",
                {**identity, "exception_type": type(error).__name__},
            )
            self._gate.finish(attempt)
            raise

        self._write("client_call_returned", {**identity, "response": response})
        self._gate.finish(attempt)
        return response


class CaseController:
    """Sequential case orchestration; no scoring or live-provider entry point.

    A returned case result is not necessarily a valid quality observation.
    The caller owns controlled cleanup and must retain the writer while any
    underlying invocation remains active.
    """

    def __init__(self, gate: AttemptGate, writer: EvidenceWriter) -> None:
        self._gate = gate
        self._writer = writer
        self._case_lock = threading.Lock()
        self._cases = 0
        self._seen: set[tuple[str, str]] = set()

    @property
    def cases_admitted(self) -> int:
        return self._cases

    def run_case(
        self,
        *,
        case_id: str,
        revision: str,
        question: str,
        client,
        agent_factory,
    ):
        if not self._case_lock.acquire(blocking=False):
            self._gate.stop()
            raise AdmissionError("Another case is already active")
        try:
            return self._run_case(
                case_id=case_id,
                revision=revision,
                question=question,
                client=client,
                agent_factory=agent_factory,
            )
        except BaseException:
            self._gate.stop()
            raise
        finally:
            self._case_lock.release()

    def _run_case(self, *, case_id, revision, question, client, agent_factory):
        if not isinstance(question, str):
            raise ValueError("question must be text")
        recording = RecordingClient(
            client, self._gate, self._writer,
            case_id=case_id, revision=revision,
        )
        self._gate.check_case_admission()
        if self._cases >= self._gate.limits.max_cases:
            raise AdmissionError("Case budget exhausted")
        key = (revision, case_id)
        if key in self._seen:
            raise AdmissionError("Case repeats are not admitted")

        self._cases += 1
        self._seen.add(key)
        identity = {
            "case_id": case_id,
            "revision": revision,
            "case_number": self._cases,
        }
        self._writer.write("case_started", {**identity, "question": question})

        # Persistence and factory construction may consume elapsed time.
        phase = "pre_construction_admission"
        try:
            self._gate.check_case_admission()
            phase = "agent_construction"
            agent = agent_factory(client=recording)
            phase = "pre_execution_admission"
            self._gate.check_case_admission()
            phase = "agent_execution"
            result = agent.run(question)
        except BaseException as error:
            self._gate.stop()
            self._writer.write(
                "case_raised",
                {
                    **identity,
                    "phase": phase,
                    "exception_type": type(error).__name__,
                },
            )
            raise

        provider_failure = any(
            event.kind == "llm_call"
            and event.detail.startswith("provider call failed:")
            for event in result.trace
        )
        unresolved = self._gate.active is not None
        if provider_failure or unresolved:
            self._gate.stop()

        # This post-return check prevents further admission after deadline expiry.
        # It does not interrupt work or retroactively make the case on-budget.
        if not self._gate.stopped:
            try:
                self._gate.check_case_admission()
            except AdmissionError:
                self._gate.stop()

        self._writer.write(
            "case_returned",
            {
                **identity,
                "provider_failure": provider_failure,
                "unresolved_invocation": unresolved,
                "admission_stopped": self._gate.stopped,
                "answer": {
                    "text": result.answer.answer,
                    "citations": list(result.answer.citations),
                    "confidence": result.answer.confidence,
                    "needs_human_review": result.answer.needs_human_review,
                },
                "trace": [
                    {"kind": event.kind, "detail": event.detail}
                    for event in result.trace
                ],
            },
        )
        return result

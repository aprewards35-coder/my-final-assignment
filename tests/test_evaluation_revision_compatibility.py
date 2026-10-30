"""Controlled compatibility checks, not evaluation or candidate approval."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REVISIONS = (
    "da5776412fe0c200201032726b7db4a2f0cce954",
    "6bb61668cd17da6f1cf7b9ad439ffce90701b271",
)

CHILD = r'''
import json
import sys
import threading
from pathlib import Path

snapshot, tooling, output, revision, scenario = sys.argv[1:]
snapshot = Path(snapshot).resolve()
sys.path.insert(0, str(snapshot))

import agent
import safety

assert Path(agent.__file__).resolve() == snapshot / "agent.py"
assert Path(safety.__file__).resolve() == snapshot / "safety.py"
assert agent.CORPUS_DIR.resolve() == snapshot / "data" / "corpus"

def forbidden_provider(*args, **kwargs):
    raise AssertionError("Default provider construction is forbidden")

agent.get_client = forbidden_provider

sys.path.insert(1, tooling)
from scripts.evaluation_controls import (
    AdmissionError, AttemptGate, CaseController, EvaluationLimits, EvidenceWriter,
)

QUESTION = "How does chunking work in RAG?"
RESPONSE = json.dumps({
    "answer": "Controlled compatibility response.",
    "citations": [],
    "confidence": 0.0,
    "needs_human_review": True,
})

def normalized(result):
    return {
        "answer": result.answer.answer,
        "citations": list(result.answer.citations),
        "confidence": result.answer.confidence,
        "needs_human_review": result.answer.needs_human_review,
        "trace": [(event.kind, event.detail) for event in result.trace],
    }

class Client:
    def __init__(self):
        self.calls = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.worker = None

    def complete(self, system, user):
        self.calls.append((system, user))
        if scenario == "repair_failure":
            if len(self.calls) == 1:
                return "{not valid JSON"
            if len(self.calls) == 2:
                raise ConnectionError("controlled repair failure")
            raise AssertionError("Unexpected third invocation")
        if scenario == "timeout":
            self.worker = threading.current_thread()
            self.started.set()
            if not self.release.wait(10):
                raise RuntimeError("Controlled release was not observed")
        return RESPONSE

direct = None
if scenario != "timeout":
    direct_client = Client()
    direct = agent.YourAgent(client=direct_client).run(QUESTION)

writer = EvidenceWriter(Path(output))
gate = AttemptGate(EvaluationLimits(), clock=lambda: 0.0)
controller = CaseController(gate, writer)
underlying = Client()
outcome = {}
caller = None

def records():
    return [json.loads(line) for line in writer.path.read_text().splitlines()]

def factory(*, client):
    instance = agent.YourAgent(client=client)
    if scenario == "timeout":
        instance.timeout_s = 0.1
    return instance

def invoke():
    try:
        outcome["result"] = controller.run_case(
            case_id=scenario,
            revision=revision,
            question=QUESTION,
            client=underlying,
            agent_factory=factory,
        )
    except BaseException as error:
        outcome["error"] = error

def reject_next_case():
    before = len(underlying.calls)
    try:
        controller.run_case(
            case_id="must-not-dispatch",
            revision=revision,
            question=QUESTION,
            client=underlying,
            agent_factory=factory,
        )
    except AdmissionError:
        pass
    else:
        raise AssertionError("Another case was admitted")
    assert len(underlying.calls) == before
    assert controller.cases_admitted == 1

try:
    if scenario == "timeout":
        caller = threading.Thread(target=invoke, daemon=True)
        caller.start()
        assert underlying.started.wait(2), "Controlled invocation did not start"
        caller.join(3)
        assert not caller.is_alive(), "Application caller did not return"
    else:
        invoke()

    if "error" in outcome:
        raise outcome["error"]
    result = outcome["result"]
    rows = records()
    starts = [row for row in rows if row["event"] == "attempt_started"]
    terminal = next(row for row in rows if row["event"] == "case_returned")

    assert starts
    assert all(row["data"]["revision"] == revision for row in starts)
    assert [
        (row["data"]["system"], row["data"]["user"]) for row in starts
    ] == underlying.calls

    extension = (
        "\\n" + agent.PROMPT_EXTENSION
        if revision == "da5776412fe0c200201032726b7db4a2f0cce954"
        else "\n" + agent.PROMPT_EXTENSION
    )
    assert all(system.endswith(extension) for system, _ in underlying.calls)

    if scenario != "timeout":
        assert normalized(result) == normalized(direct)
        assert underlying.calls == direct_client.calls
        assert gate.active is None

    if scenario == "valid_response":
        assert len(starts) == 1
        assert not gate.stopped
        assert not terminal["data"]["provider_failure"]
        assert not terminal["data"]["unresolved_invocation"]

    elif scenario == "repair_failure":
        attempts = [
            row for row in rows
            if row["event"] in {
                "attempt_started", "client_call_returned", "client_call_raised"
            }
        ]
        assert [row["event"] for row in attempts] == [
            "attempt_started", "client_call_returned",
            "attempt_started", "client_call_raised",
        ]
        assert [row["data"]["attempt_id"] for row in attempts] == [1, 1, 2, 2]
        assert attempts[1]["data"]["response"] == "{not valid JSON"
        assert attempts[3]["data"]["exception_type"] == "ConnectionError"
        assert [event.kind for event in result.trace] == [
            "retrieve", "llm_call", "decision"
        ]
        assert terminal["data"]["provider_failure"]
        assert gate.stopped
        reject_next_case()

    else:
        assert result.answer.needs_human_review
        assert any(
            event.kind == "llm_call"
            and event.detail == "provider call failed: TimeoutError"
            for event in result.trace
        )
        assert underlying.worker.is_alive()
        assert gate.active == 1
        assert gate.stopped
        assert terminal["data"]["unresolved_invocation"]
        assert terminal["data"]["provider_failure"]
        assert not any(row["event"] == "client_call_returned" for row in rows)
        reject_next_case()

        underlying.release.set()
        underlying.worker.join(3)
        assert not underlying.worker.is_alive()
        assert gate.active is None
        assert gate.stopped
        late = next(
            row for row in records() if row["event"] == "client_call_returned"
        )
        assert late["sequence"] > terminal["sequence"]
        reject_next_case()

    stops = [
        row for row in records() if row["event"] == "run_admission_stopped"
    ]
    assert len(stops) == (0 if scenario == "valid_response" else 1)
    if stops:
        assert stops[0]["data"]["provider_work_termination_verified"] is False
finally:
    underlying.release.set()
    if caller is not None:
        caller.join(3)
    if underlying.worker is not None:
        underlying.worker.join(3)
    caller_done = caller is None or not caller.is_alive()
    worker_done = underlying.worker is None or not underlying.worker.is_alive()
    if caller_done and worker_done:
        writer.close()
    else:
        raise AssertionError("Controlled cleanup incomplete; writer not closed")

print(json.dumps({
    "revision": revision,
    "scenario": scenario,
    "controlled_compatibility_verified": True,
    "live_execution_authorized": False,
    "candidate_approval": False,
}))
'''


def git_bytes(*arguments: str) -> bytes:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, timeout=10
    )


@pytest.mark.parametrize("revision", REVISIONS)
@pytest.mark.parametrize(
    "scenario", ["valid_response", "repair_failure", "timeout"]
)
def test_exact_revision_controlled_compatibility(
    tmp_path: Path, revision: str, scenario: str
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    paths = git_bytes(
        "ls-tree", "-r", "--name-only", revision, "--",
        "agent.py", "safety.py", "data/corpus",
    ).decode().splitlines()
    assert "agent.py" in paths
    assert "safety.py" in paths
    assert any(path.startswith("data/corpus/") for path in paths)

    for relative in paths:
        destination = snapshot / relative
        assert snapshot.resolve() in destination.resolve().parents
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = git_bytes("show", f"{revision}:{relative}")
        destination.write_bytes(source)
        assert hashlib.sha256(destination.read_bytes()).digest() == (
            hashlib.sha256(source).digest()
        )

    script = tmp_path / "controlled_check.py"
    script.write_text(CHILD)
    output = tmp_path / "evidence"
    output.mkdir()
    environment = os.environ.copy()
    environment.update(
        BOOTCAMP_PROVIDER="fake",
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    for name in ("PYTHONPATH", "GH_TOKEN", "GITHUB_TOKEN"):
        environment.pop(name, None)

    result = subprocess.run(
        [
            sys.executable, "-I", "-B", str(script),
            str(snapshot), str(ROOT), str(output), revision, scenario,
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"revision={revision} scenario={scenario}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

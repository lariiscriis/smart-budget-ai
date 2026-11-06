"""Isolated worker -> n8n bridge -> authenticated backend -> persisted result."""
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import automation_worker as worker
from app.auth import utcnow
from app.main import app
from app.models import AuthSession, AutomationJob, Expense
from app.services import automation_summary, policy_retrieval
from test_financial_entries_api import client, category
from test_auth_security import other_client


def scope(client):
    return {"workspace_id": client.test_workspace_id, "actor_id": client.test_user_id}


def enqueue(client, days=("2026-11-05",)):
    cat = category(client, name="Ingredientes")
    content = "categoria_id;descricao;data;valor\n" + "".join(
        f"{cat};Importação fictícia {index};{day};10.00\n" for index, day in enumerate(days)
    )
    preview = client.post("/imports/expenses/preview", files={"file": ("test.csv", content.encode())})
    assert preview.status_code == 200, preview.text
    batch = preview.json()
    result = client.post(f"/imports/{batch['import_id']}/confirm", json={})
    assert result.status_code == 200, result.text
    return batch, client.get("/automations").json()


@pytest.fixture
def bridge(client, monkeypatch):
    monkeypatch.setattr(worker, "engine", client.test_engine)
    monkeypatch.setattr(automation_summary.settings, "ai_mode", "gemini")
    monkeypatch.setattr(automation_summary.settings, "gemini_api_key", SecretStr("secret-provider-key"))
    state = SimpleNamespace(payloads=[], queries=[], responses=[], behavior=None)
    class RagClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def search(db, client, question):
        state.queries.append(dict(db.info))
        assert db.info["actor_kind"] == "automation"
        assert db.info["automation_job_id"] > 0
        return []  # Supplemental retrieval still reads the real Markdown corpus.
    monkeypatch.setattr(automation_summary.genai, "Client", RagClient)
    monkeypatch.setattr(policy_retrieval, "search_financial_policies", search)
    api = TestClient(app)
    def fetch(payload):
        params = {key: payload[key] for key in ("year", "month", "workspace_id", "import_id", "attempt")}
        return api.get(f"/automations/{payload['job_id']}/analysis", params=params,
                       headers={"Authorization": f"Bearer {payload['api_token']}"})
    state.fetch = fetch
    class WorkflowClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, json):
            state.payloads.append(json)
            if state.behavior:
                return state.behavior(json)
            response = fetch(json)
            state.responses.append(response)
            return response
    monkeypatch.setattr(worker.httpx, "Client", WorkflowClient)
    return state


def latest(client):
    return client.get("/automations").json()[0]


def test_completed_import_uses_policies_and_is_processed_once(client, bridge):
    batch, jobs = enqueue(client)
    assert len(jobs) == 1 and jobs[0]["status"] == "pending"
    # Confirmation is already transactional and idempotent; do not enqueue again.
    repeated = client.post(f"/imports/{batch['import_id']}/confirm", json={})
    assert repeated.json()["already_completed"] is True
    assert worker.process_one() is True
    assert worker.process_one() is False
    job = latest(client)
    assert job["status"] == "succeeded" and job["attempts"] == 1
    result = job["result"]
    assert result["context"] == {
        "job_id": job["id"], "import_id": batch["import_id"], "workspace_id": client.test_workspace_id,
        "year": 2026, "month": 11, "attempt": 1, "actor_kind": "automation",
    }
    assert result["summary"]["actual"] == "10.00"
    assert result["alerts"]["alerts"][0]["code"] == "unbudgeted"
    tool = result["analysis"]["tools_used"][0]
    assert {"ORC-04", "DEC-01", "DEC-02", "DEC-03"} <= {source["section_id"] for source in tool["sources"]}
    for text in ["todo o mês", "Dúvidas", "Sugestões", "não grava, aprova, altera orçamento nem dispara automações"]:
        assert text in result["analysis"]["answer"]
    assert len(bridge.queries) == len(bridge.payloads) == 1
    assert bridge.queries[0]["workspace_id"] == client.test_workspace_id
    assert bridge.queries[0]["automation_attempt"] == 1
    token = bridge.payloads[0]["api_token"]
    assert token not in json.dumps(job) and "secret-provider-key" not in json.dumps(job)
    assert client.post(f"/automations/{job['id']}/retry").status_code == 409
    with Session(client.test_engine) as db:
        assert db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()) is None
        assert len(db.scalars(select(Expense)).all()) == 1
    audit = client.get("/audit?limit=100").json()
    changes = [item for item in audit if item["entity"] == "automation_jobs" and item["action"] == "update"]
    assert changes and all(item["actor_kind"] == "automation" for item in changes)


def test_multiple_periods_produce_one_job_each(client, bridge):
    _, jobs = enqueue(client, ("2026-11-05", "2026-11-06", "2026-12-01"))
    assert len(jobs) == 2
    assert worker.process_one() and worker.process_one() and not worker.process_one()
    assert {item["status"] for item in client.get("/automations").json()} == {"succeeded"}
    assert [item["month"] for item in bridge.payloads] == [11, 12]


def test_n8n_unavailable_preserves_task_and_retry_revokes_tokens(client, bridge, capsys):
    enqueue(client)
    def offline(payload):
        raise httpx.ConnectError(f"Untrusted details: {payload['api_token']} secret-provider-key")
    bridge.behavior = offline
    assert worker.process_one()
    failed = latest(client)
    assert failed["status"] == "failed" and failed["last_error"] == "ConnectError"
    assert failed["result"] is None
    token = bridge.payloads[0]["api_token"]
    assert token not in capsys.readouterr().out
    assert "secret-provider-key" not in json.dumps(failed)
    assert client.post(f"/automations/{failed['id']}/retry").status_code == 200
    assert client.post(f"/automations/{failed['id']}/retry").status_code == 409
    bridge.behavior = None
    assert worker.process_one()
    assert latest(client)["status"] == "succeeded" and latest(client)["attempts"] == 2
    assert bridge.payloads[0]["api_token"] != bridge.payloads[1]["api_token"]
    assert bridge.fetch(bridge.payloads[0]).status_code == 401


def test_lost_response_retry_reuses_cached_analysis(client, bridge):
    enqueue(client)
    def lost(payload):
        response = bridge.fetch(payload)
        assert response.status_code == 200, response.text
        # A repeated callback during the same attempt also reuses the cache.
        assert bridge.fetch(payload).json() == response.json()
        raise httpx.ReadTimeout("Response lost after successful backend generation")
    bridge.behavior = lost
    assert worker.process_one()
    failed = latest(client)
    assert failed["status"] == "failed" and failed["result"] is not None
    assert len(bridge.queries) == 1
    assert client.post(f"/automations/{failed['id']}/retry").status_code == 200
    bridge.behavior = None
    assert worker.process_one()
    done = latest(client)
    assert done["status"] == "succeeded" and done["result"]["context"]["attempt"] == 2
    assert done["result"]["analysis"] == failed["result"]["analysis"]
    assert len(bridge.queries) == 1


def test_workflow_cannot_modify_backend_answer(client, bridge):
    enqueue(client)
    def forged(payload):
        response = bridge.fetch(payload)
        assert response.status_code == 200
        data = response.json()
        data["analysis"]["answer"] = "APROVADO: altere o orçamento"
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: data)
    bridge.behavior = forged
    assert worker.process_one()
    job = latest(client)
    assert job["status"] == "failed" and job["last_error"] == "WorkflowResultMismatch"
    assert "APROVADO" not in job["result"]["analysis"]["answer"]


def test_rag_failure_is_sanitized_and_retryable(client, bridge, monkeypatch, caplog):
    enqueue(client)
    def unavailable(*args):
        raise RuntimeError("Provider secret-provider-key; index unavailable")
    monkeypatch.setattr(policy_retrieval, "search_financial_policies", unavailable)
    assert worker.process_one()
    job = latest(client)
    assert job["status"] == "failed" and job["result"] is None
    assert "secret-provider-key" not in caplog.text
    assert "secret-provider-key" not in bridge.responses[0].text
    assert client.post(f"/automations/{job['id']}/retry").status_code == 200


def test_mock_mode_does_not_pretend_to_have_retrieved_policies(client, bridge, monkeypatch):
    enqueue(client)
    monkeypatch.setattr(automation_summary.settings, "ai_mode", "mock")
    assert worker.process_one()
    job = latest(client)
    assert job["status"] == "failed" and job["result"] is None
    assert bridge.queries == []


def test_stale_running_job_is_recovered_and_can_retry(client, bridge):
    _, jobs = enqueue(client)
    job_id = jobs[0]["id"]
    with Session(client.test_engine, info=scope(client)) as db:
        job = db.get(AutomationJob, job_id)
        job.status, job.attempts = "running", 1
        db.add(AuthSession(token_hash="c" * 64, user_id=client.test_user_id,
                           workspace_id=client.test_workspace_id, job_id=job_id,
                           expires_at=utcnow() - timedelta(seconds=1)))
        db.commit()
    with client.test_engine.begin() as connection:
        connection.execute(AutomationJob.__table__.update().where(AutomationJob.id == job_id).values(
            updated_at=utcnow() - timedelta(seconds=worker.LEASE_SECONDS + 1)))
    assert not worker.process_one()
    assert latest(client)["last_error"] == "WorkerLeaseExpired"
    with Session(client.test_engine) as db:
        assert db.get(AuthSession, "c" * 64) is None
    assert client.post(f"/automations/{job_id}/retry").status_code == 200
    assert worker.process_one()
    assert latest(client)["status"] == "succeeded" and latest(client)["attempts"] == 2


def test_late_attempt_cannot_overwrite_new_success(client, bridge):
    enqueue(client)
    def late(payload):
        first = bridge.fetch(payload)
        assert first.status_code == 200, first.text
        with Session(client.test_engine, info=scope(client)) as db:
            db.get(AutomationJob, payload["job_id"]).status = "failed"
            db.commit()
        assert client.post(f"/automations/{payload['job_id']}/retry").status_code == 200
        bridge.behavior = None
        assert worker.process_one()  # New attempt finishes before the old reply.
        return first
    bridge.behavior = late
    assert worker.process_one()
    job = latest(client)
    assert job["status"] == "succeeded" and job["attempts"] == 2
    assert job["result"]["context"]["attempt"] == 2
    assert len(bridge.queries) == 1


def test_capability_context_and_workspace_cannot_be_changed(client, bridge):
    _, jobs = enqueue(client)
    outsider = other_client(client, separate_workspace=True)
    assert outsider.post(f"/automations/{jobs[0]['id']}/retry").status_code == 404
    assert client.get(f"/automations/{jobs[0]['id']}/analysis").status_code == 403
    def restricted(payload):
        for key, value in [("workspace_id", 99999), ("import_id", "other-import"), ("attempt", 99), ("month", 12)]:
            changed = {**payload, key: value}
            assert bridge.fetch(changed).status_code == 403
        assert bridge.fetch({**payload, "job_id": 99999}).status_code == 403
        return bridge.fetch(payload)
    bridge.behavior = restricted
    assert worker.process_one()
    assert latest(client)["status"] == "succeeded"
    assert outsider.get("/automations").json() == []


def test_exported_workflow_is_single_scoped_read_and_no_execution_data():
    workflows = Path(__file__).resolve().parents[1] / "workflows"
    assert len(list(workflows.glob("*.json"))) == 1
    data = json.loads(next(workflows.glob("*.json")).read_text(encoding="utf-8"))
    assert [node["type"] for node in data["nodes"]] == [
        "n8n-nodes-base.webhook", "n8n-nodes-base.httpRequest", "n8n-nodes-base.respondToWebhook",
    ]
    node = data["nodes"][1]
    assert "/analysis" in node["parameters"]["url"]
    assert {item["name"] for item in node["parameters"]["queryParameters"]["parameters"]} == {
        "year", "month", "workspace_id", "import_id", "attempt",
    }
    assert "api_token" in node["parameters"]["headerParameters"]["parameters"][0]["value"]
    assert data["settings"]["saveDataErrorExecution"] == data["settings"]["saveDataSuccessExecution"] == "none"
    assert data["settings"]["saveManualExecutions"] is False
    assert data["settings"]["saveExecutionProgress"] is False
    assert data["pinData"] == {} and data["active"] is False

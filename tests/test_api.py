"""Integration tests: full lifecycle of a process through the REST API."""
from fastapi.testclient import TestClient

from app.main import app

PDF = ("doc.pdf", b"%PDF-1.4 test", "application/pdf")


def _create(client):
    res = client.post("/api/processes", json={"template_key": "admin_purchase",
                                              "name": "Compra de prueba", "owner": "Tester QA"})
    assert res.status_code == 201
    return res.json()


def test_templates_available():
    with TestClient(app) as client:
        keys = {t["key"] for t in client.get("/api/templates").json()}
        assert {"academic_thesis", "admin_purchase", "business_project"} <= keys


def test_ai_gate_blocks_then_allows_advance():
    with TestClient(app) as client:
        process = _create(client)
        phase1 = process["phases"][0]
        assert phase1["status"] == "in_progress"

        # Advancing an empty phase must be blocked by the AI
        res = client.post(f"/api/phases/{phase1['id']}/advance").json()
        assert res["advanced"] is False
        assert res["process"]["status"] == "blocked"
        assert client.get("/api/alerts").json()

        # Complete the requirements and advance
        client.put(f"/api/phases/{phase1['id']}/submission", json={"fields": {
            "need": "Compra de licencias de software para el laboratorio de redes de la facultad.",
            "area": "Ingeniería", "budget": 1000000}})
        client.post(f"/api/phases/{phase1['id']}/documents", data={"key": "request_doc"}, files={"file": PDF})
        res = client.post(f"/api/phases/{phase1['id']}/advance").json()
        assert res["advanced"] is True
        assert res["process"]["current_phase_order"] == 2
        assert res["process"]["status"] == "active"

        # Phase 1 is now closed for edition
        assert client.put(f"/api/phases/{phase1['id']}/submission", json={"fields": {}}).status_code == 409

        # Cross-phase inconsistency in phase 2 (quote above budget)
        phase2 = res["process"]["phases"][1]
        client.put(f"/api/phases/{phase2['id']}/submission", json={"fields": {
            "quotes_count": 3, "supplier": "Proveedor", "quoted_amount": 2000000}})
        client.post(f"/api/phases/{phase2['id']}/documents", data={"key": "quotes_doc"}, files={"file": PDF})
        validation = client.post(f"/api/phases/{phase2['id']}/validate").json()
        assert validation["passed"] is False
        assert any(f["category"] == "consistency" for f in validation["findings"])

        report = client.get(f"/api/processes/{process['id']}/report").json()
        assert report["overview"]["progress"] == 25.0
        assert client.get(f"/api/processes/{process['id']}/report.html").status_code == 200


def test_rejects_unknown_document_key():
    with TestClient(app) as client:
        process = _create(client)
        phase_id = process["phases"][0]["id"]
        res = client.post(f"/api/phases/{phase_id}/documents", data={"key": "nope"}, files={"file": PDF})
        assert res.status_code == 409

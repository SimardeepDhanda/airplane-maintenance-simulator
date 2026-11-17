import pytest
from fastapi.testclient import TestClient

from app import __version__


@pytest.mark.db
def test_health_ok_when_database_reachable(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "version": __version__}


def test_health_degraded_when_database_unreachable(client_without_db: TestClient) -> None:
    response = client_without_db.get("/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": "unavailable",
        "version": __version__,
    }


def test_openapi_documents_health_contract(client_without_db: TestClient) -> None:
    spec = client_without_db.get("/openapi.json").json()
    responses = spec["paths"]["/health"]["get"]["responses"]
    assert {"200", "503"} <= set(responses)
    assert spec["components"]["schemas"]["HealthResponse"]["required"] == [
        "status",
        "database",
        "version",
    ]

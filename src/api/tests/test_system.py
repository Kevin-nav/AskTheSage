
from fastapi.testclient import TestClient

def test_get_system_status(authenticated_client: TestClient):
    # Act
    response = authenticated_client.get("/api/v1/admin/system/status")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["database_status"] == "ok"
    assert data["api_status"] == "ok"

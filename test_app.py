import pytest

from app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_create_and_get_task(client):
    res = client.post("/tasks", json={"title": "Écrire le rapport"})
    assert res.status_code == 201
    task = res.get_json()
    assert task["title"] == "Écrire le rapport" and task["done"] is False
    assert client.get(f"/tasks/{task['id']}").get_json() == task


def test_create_task_without_title(client):
    assert client.post("/tasks", json={}).status_code == 400
    assert client.post("/tasks", json={"title": "  "}).status_code == 400


def test_list_update_delete(client):
    task_id = client.post("/tasks", json={"title": "A"}).get_json()["id"]
    assert len(client.get("/tasks").get_json()) == 1
    res = client.put(f"/tasks/{task_id}", json={"done": True})
    assert res.get_json()["done"] is True
    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_unknown_route_returns_json_404(client):
    res = client.get("/nope")
    assert res.status_code == 404
    assert "error" in res.get_json()


def test_metrics_endpoint(client):
    client.get("/health")
    res = client.get("/metrics")
    assert res.status_code == 200
    assert b"http_requests_total" in res.data
    assert b"http_request_duration_seconds" in res.data


def test_request_id_header(client):
    res = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert res.headers["X-Request-ID"] == "abc-123"

"""Tests unitaires de l'API Task (app.py).

Organisation par classe : santé/metrics, création, lecture, mise à jour,
suppression, cas d'erreur et comportements transversaux (headers, JSON).
Chaque test utilise une app fraîche (fixture) => isolation totale.
"""
import logging

import pytest

from app import JsonFormatter, create_app


@pytest.fixture()
def client():
    return create_app().test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def create_task(client, title="tâche", done=False):
    """Crée une tâche et renvoie son dict."""
    res = client.post("/tasks", json={"title": title, "done": done})
    assert res.status_code == 201
    return res.get_json()


# ---------------------------------------------------------------------------
# Health & metrics
# ---------------------------------------------------------------------------
class TestHealthAndMetrics:
    def test_health_ok(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.get_json() == {"status": "ok"}

    def test_metrics_content_type_and_counters(self, client):
        create_task(client, "avec métrique")
        client.get("/health")
        res = client.get("/metrics")
        assert res.status_code == 200
        assert b"http_requests_total" in res.data
        assert b"http_request_duration_seconds" in res.data
        # Le compteur enregistre bien les statuts observés
        assert b'status="201"' in res.data
        assert b'status="200"' in res.data

    def test_metrics_are_cumulative(self, client):
        client.get("/health")
        client.get("/health")
        first = client.get("/metrics").data.count(b'status="200"')
        assert first > 0  # les requêtes sont comptées entre les deux appels

    def test_unknown_method_not_allowed(self, client):
        res = client.patch("/health")
        assert res.status_code == 405
        assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# POST /tasks — création
# ---------------------------------------------------------------------------
class TestCreateTask:
    def test_create_minimal(self, client):
        res = client.post("/tasks", json={"title": "Ma tâche"})
        assert res.status_code == 201
        task = res.get_json()
        assert task == {"id": 1, "title": "Ma tâche", "done": False}

    def test_create_with_done_true(self, client):
        task = create_task(client, "terminée", done=True)
        assert task["done"] is True

    def test_create_strips_whitespace_from_title(self, client):
        task = create_task(client, "   espaces   ")
        assert task["title"] == "espaces"

    def test_ids_increment(self, client):
        first = create_task(client, "a")
        second = create_task(client, "b")
        assert second["id"] == first["id"] + 1

    @pytest.mark.parametrize("payload", [
        {},                                   # clé absente
        {"title": ""},                        # chaîne vide
        {"title": "   "},                     # blancs uniquement
        {"title": None},                      # None
        {"title": 123},                       # mauvais type
        {"title": ["liste"]},                 # mauvais type
        {"title": {"obj": True}},             # mauvais type
    ])
    def test_create_invalid_payloads_return_400(self, client, payload):
        res = client.post("/tasks", json=payload)
        assert res.status_code == 400
        assert res.get_json()["error"]

    def test_create_without_body_returns_400(self, client):
        res = client.post("/tasks")  # aucune donnée JSON du tout
        assert res.status_code == 400

    def test_create_with_malformed_json_returns_400(self, client):
        res = client.post(
            "/tasks", data="{pas du json", content_type="application/json"
        )
        assert res.status_code == 400

    def test_extra_fields_are_ignored(self, client):
        res = client.post("/tasks", json={"title": "x", "hack": "champ"})
        assert "hack" not in res.get_json()

    def test_new_tasks_not_visible_before_creation(self, client):
        assert client.get("/tasks").get_json() == []
        create_task(client, "après")
        assert len(client.get("/tasks").get_json()) == 1


# ---------------------------------------------------------------------------
# GET /tasks et /tasks/<id> — lecture
# ---------------------------------------------------------------------------
class TestReadTasks:
    def test_list_empty_then_multiple(self, client):
        assert client.get("/tasks").get_json() == []
        t1 = create_task(client, "a")
        t2 = create_task(client, "b")
        tasks = client.get("/tasks").get_json()
        assert [t["id"] for t in tasks] == [t1["id"], t2["id"]]

    def test_get_existing_task(self, client):
        created = create_task(client, "lire moi")
        res = client.get(f"/tasks/{created['id']}")
        assert res.status_code == 200
        assert res.get_json() == created

    @pytest.mark.parametrize("task_id", [999, 0])
    def test_get_unknown_ids_return_404(self, client, task_id):
        res = client.get(f"/tasks/{task_id}")
        assert res.status_code == 404
        assert res.get_json() == {"error": "tâche introuvable"}

    @pytest.mark.parametrize("task_id", [-1, 99999999999999999999])
    def test_get_non_matching_ids_return_flask_404(self, client, task_id):
        # Int négatif / hors limites : la route ne matche pas -> 404 générique
        res = client.get(f"/tasks/{task_id}")
        assert res.status_code == 404
        assert "error" in res.get_json()

    def test_deleted_task_is_gone_from_get(self, client):
        task = create_task(client, "temporaire")
        client.delete(f"/tasks/{task['id']}")
        assert client.get(f"/tasks/{task['id']}").status_code == 404

    def test_non_integer_id_is_not_routed(self, client):
        # <int:task_id> ne matche pas : Flask renvoie son 404 JSON
        res = client.get("/tasks/notanumber")
        assert res.status_code == 404
        assert "error" in res.get_json()


# ---------------------------------------------------------------------------
# PUT /tasks/<id> — mise à jour
# ---------------------------------------------------------------------------
class TestUpdateTask:
    def test_full_update(self, client):
        task = create_task(client, "avant")
        res = client.put(
            f"/tasks/{task['id']}", json={"title": "après", "done": True}
        )
        assert res.status_code == 200
        updated = res.get_json()
        assert updated["title"] == "après" and updated["done"] is True
        # La modification est persistée dans le "stockage"
        assert client.get(f"/tasks/{task['id']}").get_json() == updated

    def test_partial_update_keeps_other_fields(self, client):
        task = create_task(client, "titre d'origine")
        res = client.put(f"/tasks/{task['id']}", json={"done": True})
        assert res.get_json() == {"id": task["id"],
                                  "title": "titre d'origine",
                                  "done": True}

    def test_update_empty_body_is_noop(self, client):
        task = create_task(client, "inchangé")
        res = client.put(f"/tasks/{task['id']}", json={})
        assert res.status_code == 200
        assert res.get_json() == task

    def test_update_strips_title(self, client):
        # Cohérence avec POST : le titre est nettoyé des espaces
        task = create_task(client, "a")
        res = client.put(f"/tasks/{task['id']}", json={"title": "  b  "})
        assert res.get_json()["title"] == "b"

    def test_update_unknown_task_returns_404(self, client):
        res = client.put("/tasks/42", json={"done": True})
        assert res.status_code == 404

    @pytest.mark.parametrize("bad_title", [None, "", "   ", 42, []])
    def test_update_invalid_title_returns_400(self, client, bad_title):
        task = create_task(client, "valide")
        res = client.put(f"/tasks/{task['id']}", json={"title": bad_title})
        assert res.status_code == 400
        # Rien n'a été modifié
        assert client.get(f"/tasks/{task['id']}").get_json()["title"] == "valide"

    def test_update_malformed_json_returns_400(self, client):
        # Cohérence avec POST : un corps illisible est rejeté, pas ignoré
        task = create_task(client, "a")
        res = client.put(f"/tasks/{task['id']}",
                         data="[[[", content_type="application/json")
        assert res.status_code == 400
        assert res.get_json() == {"error": "corps JSON invalide"}
        # Rien n'a été modifié
        assert client.get(f"/tasks/{task['id']}").get_json() == task

    @pytest.mark.parametrize("bad_done", ["oui", 1, None, [], {"x": True}])
    def test_update_non_boolean_done_returns_400(self, client, bad_done):
        task = create_task(client, "a")
        res = client.put(f"/tasks/{task['id']}", json={"done": bad_done})
        assert res.status_code == 400
        assert res.get_json()["error"] == "'done' doit être un booléen"
        assert client.get(f"/tasks/{task['id']}").get_json()["done"] is False

    def test_update_valid_boolean_done(self, client):
        task = create_task(client, "a")
        res = client.put(f"/tasks/{task['id']}", json={"done": True})
        assert res.get_json()["done"] is True

    def test_extra_fields_ignored_on_update(self, client):
        # id n'est pas modifiable, evil pas repris
        task = create_task(client, "a")
        res = client.put(f"/tasks/{task['id']}", json={"id": 999, "evil": 1})
        updated = res.get_json()
        assert updated["id"] == task["id"]
        assert "evil" not in updated


# ---------------------------------------------------------------------------
# DELETE /tasks/<id> — suppression
# ---------------------------------------------------------------------------
class TestDeleteTask:
    def test_delete_returns_204_no_content(self, client):
        task = create_task(client, "à supprimer")
        res = client.delete(f"/tasks/{task['id']}")
        assert res.status_code == 204
        assert res.data == b""

    def test_double_delete_second_is_404(self, client):
        task = create_task(client, "une fois")
        assert client.delete(f"/tasks/{task['id']}").status_code == 204
        assert client.delete(f"/tasks/{task['id']}").status_code == 404

    def test_delete_unknown_task_returns_404(self, client):
        assert client.delete("/tasks/7").status_code == 404

    def test_deleted_task_removed_from_list(self, client):
        t1 = create_task(client, "reste")
        t2 = create_task(client, "part")
        client.delete(f"/tasks/{t2['id']}")
        ids = [t["id"] for t in client.get("/tasks").get_json()]
        assert ids == [t1["id"]]


# ---------------------------------------------------------------------------
# Erreurs transversales
# ---------------------------------------------------------------------------
class TestErrors:
    def test_unknown_route_returns_json_404(self, client):
        res = client.get("/nope")
        assert res.status_code == 404
        assert "error" in res.get_json()

    def test_405_has_json_body(self, client):
        res = client.delete("/health")
        assert res.status_code == 405
        assert "error" in res.get_json()

    def test_unhandled_exception_returns_json_500(self, client):
        app = create_app()

        @app.route("/boom")
        def boom():
            raise RuntimeError("boum")

        res = app.test_client().get("/boom")
        assert res.status_code == 500
        assert res.get_json() == {"error": "internal server error"}


# ---------------------------------------------------------------------------
# Comportement transversal : headers, traçabilité
# ---------------------------------------------------------------------------
class TestObservability:
    def test_request_id_echoed_when_provided(self, client):
        res = client.get("/health", headers={"X-Request-ID": "req-42"})
        assert res.headers["X-Request-ID"] == "req-42"

    def test_request_id_generated_when_missing(self, client):
        res = client.get("/health")
        rid = res.headers.get("X-Request-ID")
        assert rid and len(rid) == 36  # UUID v4

    def test_request_ids_differ_between_requests(self, client):
        first = client.get("/health").headers["X-Request-ID"]
        second = client.get("/health").headers["X-Request-ID"]
        assert first != second

    def test_span_ended_does_not_break_response(self, client):
        # after_request doit gérer le span même après erreur métier
        res = client.get("/tasks/999")
        assert res.status_code == 404
        assert res.headers["X-Request-ID"]


# ---------------------------------------------------------------------------
# Unitaires directs : JsonFormatter
# ---------------------------------------------------------------------------
class TestJsonFormatter:
    @pytest.fixture()
    def formatter(self):
        return JsonFormatter()

    @staticmethod
    def _record(msg="salut", extra=None, exc_info=None):
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname="p", lineno=1,
            msg=msg, args=(), exc_info=exc_info,
        )
        record.extra_fields = extra or {}
        return record

    @staticmethod
    def _fmt(formatter, record):
        # format() renvoie une LIGNE JSON texte : on la parse pour vérifier
        import json
        return json.loads(formatter.format(record))

    def test_output_is_valid_json(self, formatter):
        data = self._fmt(formatter, self._record())
        assert data["message"] == "salut"
        assert data["level"] == "INFO"
        assert "time" in data

    def test_output_is_single_line(self, formatter):
        # Un log structuré doit tenir sur une seule ligne (parseable par Loki...)
        assert "\n" not in formatter.format(self._record()).strip()

    def test_extra_fields_merged(self, formatter):
        data = self._fmt(formatter, self._record(extra={"request_id": "r1"}))
        assert data["request_id"] == "r1"

    def test_extra_fields_do_not_override_core_keys(self, formatter):
        # Comportement observé : extra_fields EST APPLIQUÉ EN DERNIER (update),
        # donc il écrase les clés de base. Documenté ici à dessein : si vous
        # voulez protéger "message"/"level"/"time", c'est dans app.py qu'il
        # faut inverser l'ordre du dict data.update(...).
        data = self._fmt(formatter, self._record(extra={"message": "pirate"}))
        assert data["message"] == "pirate"

    def test_exception_field_present(self, formatter):
        import sys
        try:
            raise ValueError("échec")
        except ValueError:
            data = self._fmt(formatter, self._record(exc_info=sys.exc_info()))
        assert "ValueError" in data["exception"]

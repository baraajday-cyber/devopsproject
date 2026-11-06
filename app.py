"""Task API: petite API REST Flask avec métriques, logs JSON et tracing."""
import json
import logging
import sys
import time
import uuid

from flask import Flask, Response, g, jsonify, request
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from werkzeug.exceptions import HTTPException


class JsonFormatter(logging.Formatter):
    """Formate chaque log en une ligne JSON (facile à parser)."""

    def format(self, record):
        data = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        data.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("task-api")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False

# Tracing : chaque requête crée un span, affiché sur la console
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))
tracer = provider.get_tracer("task-api")

# Métriques Prometheus
REQUESTS = Counter("http_requests_total", "Nombre de requêtes", ["method", "endpoint", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Temps de réponse", ["endpoint"])


def create_app():
    app = Flask(__name__)
    tasks = {}  # stockage en mémoire : {id: {...}}
    counter = {"next_id": 1}

    @app.before_request
    def start_request():
        g.start = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        g.span = tracer.start_span(f"{request.method} {request.path}")

    @app.after_request
    def end_request(response):
        if not hasattr(g, "span"):
            return response
        duration = time.perf_counter() - g.start
        endpoint = request.url_rule.rule if request.url_rule else "unknown"
        REQUESTS.labels(request.method, endpoint, response.status_code).inc()
        LATENCY.labels(endpoint).observe(duration)
        ctx = g.span.get_span_context()
        g.span.set_attribute("http.status_code", response.status_code)
        g.span.end()
        response.headers["X-Request-ID"] = g.request_id
        level = logging.ERROR if response.status_code >= 500 else logging.INFO
        logger.log(level, "request", extra={"extra_fields": {
            "request_id": g.request_id,
            "trace_id": format(ctx.trace_id, "032x"),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        }})
        return response

    @app.errorhandler(Exception)
    def handle_error(error):
        if isinstance(error, HTTPException):
            return jsonify(error=error.description), error.code
        logger.exception("unhandled error", extra={"extra_fields": {"request_id": g.request_id}})
        return jsonify(error="internal server error"), 500

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.get("/tasks")
    def list_tasks():
        return jsonify(list(tasks.values()))

    @app.post("/tasks")
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify(error="'title' est obligatoire"), 400
        task = {"id": counter["next_id"], "title": title.strip(), "done": bool(data.get("done", False))}
        tasks[task["id"]] = task
        counter["next_id"] += 1
        return jsonify(task), 201

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id):
        if task_id not in tasks:
            return jsonify(error="tâche introuvable"), 404
        return jsonify(tasks[task_id])

    @app.put("/tasks/<int:task_id>")
    def update_task(task_id):
        if task_id not in tasks:
            return jsonify(error="tâche introuvable"), 404
        data = request.get_json(silent=True) or {}
        if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
            return jsonify(error="'title' invalide"), 400
        tasks[task_id].update({k: data[k] for k in ("title", "done") if k in data})
        return jsonify(tasks[task_id])

    @app.delete("/tasks/<int:task_id>")
    def delete_task(task_id):
        if tasks.pop(task_id, None) is None:
            return jsonify(error="tâche introuvable"), 404
        return "", 204

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)  # dev local ; en conteneur c'est gunicorn

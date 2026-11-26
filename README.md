# Task API — Projet DevOps

API REST de gestion de tâches (Flask) avec une chaîne DevOps complète : **CI/CD GitHub Actions, analyse de sécurité (SAST + DAST), publication Docker Hub, observabilité (Prometheus/Grafana) et déploiement Kubernetes (kind)**.

> Projet réalisé dans le cadre du cours DevOps — par **baraajday-cyber** (GitHub) / **braybar** (Docker Hub).

---

## Architecture

```
Développeur ──push──> GitHub ──CI/CD──> Docker Hub ──k8s──> Cluster kind
                        │
                        ├── test   : pytest (61 tests) + Bandit (SAST)
                        ├── docker : build + smoke test + Trivy
                        ├── publish: push braybar/task-api (latest + SHA)
                        └── dast   : cluster kind + déploiement + scan ZAP
```

- **Application** : `app.py` (147 lignes) — CRUD `/tasks`, métriques Prometheus (`/metrics`), logs JSON, tracing OpenTelemetry, `X-Request-ID`.
- **Stockage** : en mémoire (dictionnaire) — volontairement simple pour le TP.
- **Conteneur** : `Dockerfile` — image `python:3.12-slim`, gunicorn, utilisateur non-root `uid 1000`.

## Démarrage rapide

### 1. En local
```powershell
pip install -r requirements.txt
python app.py            # http://localhost:5000
```

### 2. Avec Docker Compose (app + Prometheus + Grafana)
```powershell
docker compose up -d --build
# App   : http://localhost:5000
# Grafana : http://localhost:3000 (dashboard provisionné)
# Prometheus : http://localhost:9090
```

### 3. Sur Kubernetes (kind)
```powershell
kind create cluster --name taskapi
kind load docker-image braybar/task-api:latest --name taskapi
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
# app accessible via le NodePort 30080
```

## Pipeline CI/CD

Fichier : `.github/workflows/ci.yml` — déclenché sur push `main` et sur chaque PR.

| Job | Contenu | Sortie |
|---|---|---|
| `test` | 61 tests pytest + Bandit | artefacts `pytest-results` |
| `docker` | build image, smoke test `/health`, Trivy (HIGH/CRITICAL) | artefact `trivy-report` |
| `publish` | push Docker Hub (tags `latest` + SHA) — uniquement sur `main` | image publique |
| `dast` | cluster **kind**, déploiement `k8s/`, port-forward, **scan ZAP baseline** | artefact `zap-report` |

Secrets requis : `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`.

## Sécurité

- **SAST** : Bandit sur `app.py` ; **scan d'image** : Trivy (bloque sur HIGH/CRITICAL non corrigeables).
- **DAST** : OWASP ZAP baseline sur l'app déployée dans Kubernetes — résultat : **0 High, 0 Medium** (rapport : `zap/zap_report.html`).
- Conteneur non-root, image `slim`, pas de secrets en dur.

## Observabilité

- Métriques Prometheus exposées sur `/metrics` (compteur par endpoint/méthode/statut, histogramme de latence).
- Dashboard Grafana provisionné automatiquement (`grafana/`).
- Logs JSON structurés avec `request_id` et `trace_id` (OpenTelemetry).

## Tests

```powershell
pip install -r requirements-dev.txt
pytest test_app.py -v    # 61 tests : CRUD, erreurs, observabilité, logs
```

## Structure du dépôt

```
app.py               # API Flask (147 lignes, < limite de 150)
test_app.py          # 61 tests unitaires
Dockerfile           # image non-root, gunicorn
docker-compose.yml   # app + Prometheus + Grafana
k8s/                 # deployment (1 réplica, probes) + service NodePort
zap/                 # rapport DAST ZAP
.github/workflows/   # pipeline CI/CD
grafana/ prometheus/ # provisionnement de l'observabilité
docs/                # rapport de projet et plan de présentation
```

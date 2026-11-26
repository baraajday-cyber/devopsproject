# Rapport de projet DevOps

**Auteur :** Baraaj Day *(GitHub : baraajday-cyber, Docker Hub : braybar)*
**Projet :** Task API — une chaîne DevOps complète pour une API Flask de gestion de tâches

---

## 1. Objectif et périmètre

Construire de bout en bout le cycle de vie d'une petite application web : développement testé en premier (TDD), conteneurisation, pipeline CI/CD automatisée (build, tests, scans de sécurité, publication), observabilité, déploiement Kubernetes et analyse dynamique de sécurité (DAST) — le tout piloté par un workflow GitHub (Issues → branches → Pull Requests → peer review → merge).

**Application :** API REST « gestion de tâches » en Flask (147 lignes, sous la limite imposée de 150) : CRUD `/tasks`, métriques Prometheus, logs JSON, tracing OpenTelemetry, header `X-Request-ID`. Stockage volontairement en mémoire.

## 2. Pipeline CI/CD (`.github/workflows/ci.yml`)

| Job | Rôle | Résultat |
|---|---|---|
| `test` | 61 tests pytest + analyse statique Bandit | ✅ |
| `docker` | build, smoke test `/health`, scan Trivy (HIGH/CRITICAL bloquant) | ✅ |
| `publish` | push Docker Hub (`braybar/task-api` : tags `latest` + SHA du commit) — sur `main` uniquement | ✅ |
| `dast` | cluster **kind** éphémère, déploiement des manifests, port-forward, **scan OWASP ZAP baseline** | ✅ |

**Image publiée :** `braybar/task-api` — 2 tags (`latest` + SHA), ~44 Mo, `linux/amd64`.
**Livrables associés :** captures du job `publish` vert, des tags Docker Hub, et du run CI complet.

## 3. Kubernetes (étape 9)

- `k8s/deployment.yaml` : **1 réplica** (voir leçon apprise n°1), probes de *readiness* et *liveness* sur `/health`, limites CPU/RAM.
- `k8s/service.yaml` : service **NodePort 30080**.
- `Dockerfile` : exécution **non-root (`uid 1000`)**, exigence de sécurité Kubernetes.
- Vérifié localement avec `kind` : pods `Running`, app répond sur le NodePort.

## 4. Sécurité (SAST + DAST)

- **SAST** : Bandit sur le code, Trivy sur l'image — intégrés et bloquants dans la CI.
- **DAST** : OWASP ZAP baseline exécuté **dans la pipeline** sur l'app déployée dans le cluster. Résultat : **0 alerte High, 0 alerte Medium** (67 PASS ; 1 avertissement « Storable and Cacheable Content », typique d'une API sans cache HTTP). Rapport archivé en artefact à chaque exécution (`zap/zap_report.html` pour la référence locale).

## 5. Observabilité (livrable n°5)

Pile Docker Compose : app + Prometheus + Grafana. Métriques `http_requests_total` (par endpoint/méthode/statut) et histogramme de latence ; dashboard Grafana provisionné automatiquement ; logs JSON avec `request_id`/`trace_id`.

## 6. Workflow GitHub

Issues #1–#16, branches de feature, une Pull Request par étape, revue par les pairs (PR #17 revue par un camarade — « LGTM »), merges avec clôture automatique des issues (`Closes #N`). 16 issues fermées au total.

## 7. Leçons apprises

1. **Réplicas vs stockage en mémoire.** Le déploiement initial prévoyait 2 réplicas ; avec un stockage en mémoire par pod, une tâche créée dans un pod « n'existe pas » dans l'autre — `GET /tasks` devenait incohérent. Correction : **1 réplica** ; passer à N réplicas impliquerait un état partagé (Redis/Postgres). Bon rappel que la scalabilité dépend du modèle de données, pas seulement du nombre de pods.
2. **Environnements Windows : WSL2 est un prérequis réel.** L'installation de Docker Desktop a échoué plusieurs fois (codes 0xFFFFFFFD) avant de comprendre la chaîne : WSL absent → fonctionnalités Windows à activer → **redémarrage réel** (le « Fast Startup » conserve l'état et empêche l'activation) → espace disque → permissions de `C:\ProgramData\DockerDesktop` (dossier à réinitialiser). La lecture des logs d'installation (`install-log-admin.txt`) a été décisive.
3. **DAST en CI : 5 itérations de débogage.** Le scan passait dès le premier essai, mais le job échouait sur la périphérie : (1) l'action ZAP ne peut pas créer d'issue GitHub depuis une PR (permissions), (2) son nom d'artefact interne est refusé par GitHub, (3) sur un runner Linux, le volume est monté avec des permissions POSIX (fix `--user root`), (4) `host.docker.internal` n'existe pas sous Linux (fix `--network host`). Solution finale robuste : appel direct de `zap-baseline.py` en `docker run`, rapport écrit dans le workspace, artefact uploadé par `upload-artifact`.
4. **Ne pas « figer » un bug dans les tests.** Les premiers tests documentaient des comportements douteux du `PUT` (titre non nettoyé, `done` non validé, JSON malformé silencieux). Ils ont été inversés et le code corrigé — le test documente le contrat, pas l'implémentation.
5. **`kind load` plutôt que pull réseau en CI.** Charger l'image buildée dans le cluster kind évite de dépendre d'un registre (plus rapide et fiable, et compatible avec les images non publiées).

## 8. Conclusion

La chaîne complète — « **builds, tests, scans, and deploys** » — est opérationnelle et automatisée : chaque push sur `main` est testé (61 tests), analysé (Bandit + Trivy), publié sur Docker Hub, déployé dans Kubernetes et audité par ZAP, avec rapport conservé en artefact. Les limites connues (stockage en mémoire, 1 réplica, scan baseline passif) sont assumées et documentées, et constituent des pistes d'évolution naturelles.

---
*Captures à insérer : (1) run CI complet vert sur `main`, (2) tags Docker Hub, (3) dashboard Grafana, (4) pods Kubernetes `Running`, (5) rapport ZAP, (6) peer review.*

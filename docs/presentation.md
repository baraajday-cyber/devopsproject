# Plan de présentation (10-12 slides)

> À copier dans PowerPoint / Google Slides / Canva. Les captures indiquées sont dans votre dossier de captures.

---

## Slide 1 — Titre
**Task API : une chaîne DevOps complète**
Nom, cours, date.
*Capture : logo GitHub + Docker Hub côte à côte.*

## Slide 2 — L'application
API REST Flask « gestion de tâches » : CRUD, métriques Prometheus, logs JSON, tracing, non-root.
1 slide, 4 bullet points, **147 lignes** (< limite 150).
*Capture : terminal avec `pytest — 61 passed`.*

## Slide 3 — Le workflow (10 %)
Issues → branches → PR → peer review → merge.
Chiffres : **16 issues, ~10 PRs, peer review reçue (LGTM) + donnée**.
*Capture : page Issues du dépôt / commentaire LGTM de la PR #17.*

## Slide 4 — La pipeline CI/CD (schéma)
`push → test (pytest+Bandit) → docker (build+smoke+Trivy) → publish (Docker Hub) → dast (kind+ZAP)`
*Capture : le run CI avec les 4 jobs verts.*

## Slide 5 — Tests et qualité
61 tests : CRUD, cas d'erreur, observabilité, logs JSON.
Leçon : « un test documente le contrat, pas le bug » (ex. PUT corrigé grâce aux tests).

## Slide 6 — Sécurité SAST
Bandit (code) + Trivy (image, HIGH/CRITICAL bloquant).
*Capture : rapport Trivy.*

## Slide 7 — Publication
Docker Hub `braybar/task-api` : tags `latest` + SHA (tracabilité), sur `main` uniquement.
*Capture : page tags Docker Hub.*

## Slide 8 — Kubernetes
kind : deployment (1 réplica, probes /health, limites ressources) + service NodePort 30080. Non-root uid 1000.
*Capture : `kubectl get pods` Running.*

## Slide 9 — DAST avec ZAP
Scan baseline **dans la pipeline** sur l'app déployée : **0 High, 0 Medium, 67 PASS**.
Mentionner honnêtement : scan passif/baseline ; un active scan est l'évolution naturelle.
*Capture : rapport ZAP HTML.*

## Slide 10 — Observabilité
Prometheus + Grafana + logs JSON (request_id, trace_id).
*Capture : dashboard Grafana avec métriques.*

## Slide 11 — Leçons apprises (les plus valorisées)
1. Scalabilité = modèle de données (2 réplicas vs stockage mémoire).
2. Environnement Windows/WSL2 : lire les logs, redémarrer « pour de vrai ».
3. DAST en CI : 5 itérations de débogage → docker run direct.
4. Ne pas figer un bug dans les tests.

## Slide 12 — Démo + conclusion
Live possible : `docker compose up` + Grafana, ou montrer le rapport ZAP.
Chaîne complète automatisée : **builds, tests, scans, deploys** ✅

---

### Conseils de passage (5-7 minutes)
- Ouvrir avec le schéma de la pipeline (slide 4) : c'est le cœur du sujet.
- Insister sur les leçons apprises (slide 11) : c'est ce qui différencie.
- Si démo : la stack Compose tourne en 1 commande ; avoir un onglet Grafana préparé.
- Anticiper la question « pourquoi pas 2 réplicas ? » → leçon n°1, stockage partagé manquant.

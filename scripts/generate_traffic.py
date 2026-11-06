"""Génère du trafic vers l'API (succès, 400 et 404) pour alimenter le dashboard.

Usage : python scripts/generate_traffic.py [URL] [NOMBRE_DE_REQUETES]
"""
import json
import random
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 200


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as res:
            return res.status
    except urllib.error.HTTPError as err:
        return err.code


for i in range(COUNT):
    choice = random.random()
    if choice < 0.3:
        status = call("POST", "/tasks", {"title": f"tâche {i}"})
    elif choice < 0.6:
        status = call("GET", "/tasks")
    elif choice < 0.75:
        status = call("GET", "/health")
    elif choice < 0.85:
        status = call("GET", f"/tasks/{random.randint(1, 50)}")
    elif choice < 0.93:
        status = call("POST", "/tasks", {})  # 400 volontaire
    else:
        status = call("GET", "/inconnu")  # 404 volontaire
    print(i + 1, status)
    time.sleep(random.uniform(0.02, 0.15))

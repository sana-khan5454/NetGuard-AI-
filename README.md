# NetGuard AI

NetGuard AI is a Python-based network anomaly detection and incident response demo. It simulates NetFlow-style traffic logs, scores anomalies with Isolation Forest, retrieves the closest historical incident with a sentence-transformers + FAISS RAG pipeline, and exposes the workflow through FastAPI.

## Features

- Generates fake NetFlow-style CSV logs with injected anomalies.
- Detects anomalous traffic using `sklearn.ensemble.IsolationForest`.
- Converts anomaly strength to a `0-100` score and flags rows above a threshold.
- Retrieves a matching historical incident and remediation playbook using FAISS.
- Exposes `/detect` as a FastAPI POST endpoint for n8n or other automation tools.
- Includes a local n8n Docker Compose starter.

## Project Structure

```text
netguard_ai/
  api.py          FastAPI app and /detect route
  detector.py     Isolation Forest detection logic
  rag.py          FAISS + sentence-transformers incident retrieval
  simulator.py    NetFlow CSV generator
data/
  historical_incidents.json
scripts/
  generate_logs.py
  detect_csv.py
docker-compose.yml
requirements.txt
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Generate Traffic Logs

```bash
python scripts/generate_logs.py --rows 500 --output data/netflow_logs.csv
```

## Run Detection From CLI

```bash
python scripts/detect_csv.py --csv data/netflow_logs.csv --threshold 70
```

## Run FastAPI

```bash
uvicorn netguard_ai.api:app --reload
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/detect ^
  -H "Content-Type: application/json" ^
  -d "{\"csv_path\":\"data/netflow_logs.csv\",\"threshold\":70}"
```

## n8n Local Orchestration

Start n8n:

```bash
docker compose up -d n8n
```

Suggested workflow:

1. HTTP Request node: `POST http://host.docker.internal:8000/detect`
2. IF node: check whether `incidents.length > 0`
3. Slack node: send formatted incident details and remediation from each result.

The API response already includes `anomaly_score`, row details, matched historical incident, and remediation text.


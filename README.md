# NetGuard AI

NetGuard AI is a Python-based network anomaly detection and incident response demo. It simulates NetFlow-style traffic logs, scores anomalies with Isolation Forest, retrieves the closest historical incident with a sentence-transformers + FAISS RAG pipeline, and exposes the workflow through FastAPI.

## Features

- Generates fake NetFlow-style CSV logs with injected anomalies.
- Detects anomalous traffic using `sklearn.ensemble.IsolationForest`.
- Converts anomaly strength to a `0-100` score and flags rows above a threshold.
- Retrieves a matching historical incident and remediation playbook using FAISS.
- Exposes `/detect` as a FastAPI POST endpoint for n8n or other automation tools.
- Includes a local n8n Docker Compose starter and workflow template.

## System Architecture Flow

```text
CSV Log Generator
       |
       v
Pandas Loader
       |
       v
Isolation Forest (sklearn)
       |
       v
Anomaly Scorer (0-100)
       |
       v
Threshold Check (>70?)
       |
       v
Sentence Transformer (embed anomaly)
       |
       v
FAISS Vector Store (similarity search)
       |
       v
Remediation Playbook (top-1 match)
       |
       v
FastAPI /detect endpoint
       |
       v
n8n Workflow
       |
       v
Slack Alert (formatted)
```

## Module Coverage

Module 1, Traffic Log Simulator:
`scripts/generate_logs.py` writes a CSV with `timestamp`, `src_ip`, `dst_ip`, `port`, `protocol`, `bytes_sent`, `duration`, and `packets`. It injects high-byte transfers, rare-port traffic such as `4444` and `31337`, and port-scan-style rows with very short duration plus high packet counts.

Module 2, Anomaly Detection:
`netguard_ai/detector.py` loads the CSV with Pandas, trains an Isolation Forest on `port`, `bytes_sent`, `duration`, and `packets`, normalizes outlier strength to `0-100`, and returns only rows whose score is above the configured threshold.

Module 3, Vector Store and RAG Agent:
`data/historical_incidents.json` contains 12 fake incident playbooks. `netguard_ai/rag.py` embeds incident descriptions with `sentence-transformers/all-MiniLM-L6-v2`, stores them in a FAISS inner-product index, embeds each flagged anomaly description, and returns the top-1 matched resolution.

Module 4, n8n Orchestration and Slack Alert:
`netguard_ai/api.py` exposes `POST /detect`. The n8n workflow calls that route, checks whether a flagged incident exists and whether its score is above `70`, then sends a formatted Slack alert containing anomaly details and remediation text.

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
workflows/
  netguard_n8n_workflow.json
docker-compose.yml
requirements.txt
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The first RAG run downloads `sentence-transformers/all-MiniLM-L6-v2` from Hugging Face. After that, sentence-transformers can reuse the local model cache.

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
2. IF node: check whether `incident_count > 0` and the first `anomaly_score > 70`
3. Slack node: send formatted incident details and remediation text

You can import `workflows/netguard_n8n_workflow.json` into n8n as a starter workflow. Add your Slack credentials in the Slack node before activating it.

The API response includes `anomaly_score`, row details, matched historical incident, and remediation text:

```json
{
  "threshold": 70,
  "incident_count": 1,
  "incidents": [
    {
      "anomaly_score": 100.0,
      "row_details": {
        "timestamp": "2026-06-06T12:00:00+00:00",
        "src_ip": "10.1.2.3",
        "dst_ip": "192.168.1.44",
        "port": 4444,
        "protocol": "TCP",
        "bytes_sent": 5000000,
        "duration": 220.5,
        "packets": 7000
      },
      "matched_incident": {
        "incident_type": "Suspicious Reverse Shell",
        "description": "A host initiated high-volume outbound TCP traffic to port 4444, a port commonly used by reverse shell tooling.",
        "similarity": 0.82
      },
      "remediation": "Disconnect the host from the network, collect volatile evidence, terminate suspicious processes, and review recent authentication and PowerShell logs."
    }
  ]
}
```

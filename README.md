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

## Expected Pull-And-Run Flow

Stage 1, generate logs:

```bash
python generate_logs.py
```

Creates `fake_logs.csv` with exactly 500 rows: 480 normal rows and 20 obvious anomalies. The columns are `timestamp`, `src_ip`, `dst_ip`, `port`, `protocol`, `bytes_sent`, `duration`, and `packets`.

Stage 2, build the FAISS index:

```bash
python build_index.py
```

Creates:

```text
vector_store/faiss_index.bin
vector_store/incidents_map.json
```

Stage 3, run FastAPI:

```bash
uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` to see Swagger UI with `/detect`.

Stage 4, call `/detect`:

```bash
curl -X POST http://localhost:8000/detect ^
  -H "Content-Type: application/json" ^
  -d "{\"run_detection\":true}"
```

The response includes `flagged_count` and an `incidents` list. Each incident has `src_ip`, `dst_ip`, `port`, `bytes_sent`, `duration`, `packets`, `anomaly_score`, `matched_incident`, and `remediation`.

Stage 5, run n8n:

```bash
docker compose up -d n8n
```

Import `workflows/netguard_n8n_workflow.json`, add your Slack credentials, and activate it. The IF node blocks Slack when `flagged_count` is `0`; otherwise it sends one formatted alert with each flagged incident as a separate block.

## Project Structure

```text
api/
  main.py         FastAPI import path for uvicorn api.main:app
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
build_index.py
generate_logs.py
main.py
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
python generate_logs.py
```

## Run Detection From CLI

```bash
python scripts/detect_csv.py --csv fake_logs.csv --threshold 70
```

## Run FastAPI

```bash
uvicorn api.main:app --reload --port 8000
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/detect ^
  -H "Content-Type: application/json" ^
  -d "{\"run_detection\":true}"
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
  "flagged_count": 1,
  "incidents": [
    {
      "src_ip": "192.168.1.45",
      "dst_ip": "185.23.44.1",
      "port": 31337,
      "bytes_sent": 967000,
      "duration": 0.03,
      "packets": 910,
      "anomaly_score": 91.0,
      "matched_incident": "Port Scan",
      "remediation": "Block source IP at firewall. Enable IDS rule for rare ports. Review outbound traffic logs."
    }
  ]
}
```

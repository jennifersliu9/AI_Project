# Harborline AI Engineering Project

Fictional Harborline Technologies policies plus HarborHub-style employee records, with a **seeded retrieval app** for employee questions about PTO, holidays, remote work, expenses, security, benefits, onboarding, equipment, leave, and conduct.

- Policies: `[corpus/README.md](corpus/README.md)`
- Structured records: `[data/README.md](data/README.md)`
- Gold questions: `[eval/gold_questions.json](eval/gold_questions.json)`
- Agent/Q&A gold tasks: `[eval/eval_tasks.json](eval/eval_tasks.json)`
- Latest metrics: `[eval/REPORT.md](eval/REPORT.md)`

Default answer mode is **retrieve-only**. It does not need an API key. Set `HARBORLINE_ANSWER_MODE=llm` and `OPENAI_API_KEY` only if you want a generated answer.

### FLAG — EXTERNAL vs what Cursor can do


| Cursor / this repo can do                                                                     | EXTERNAL (you must do outside this chat)                                                        |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Write `harborline/tools.py`, `mcp_server.py`, `mcp_client.py`, `.cursor/mcp.json`, CLI, tests | **Enable MCP** in Cursor Settings and allow the `harborline` server                             |
| Agent calls tools via MCP `tools/list` + `tools/call` (stdio or in-process FastMCP)           | **Restart Cursor** after changing `mcp.json` so the stdio server is relaunched                  |
| Retrieve-only answers, rewrite, rerank, guardrails, FAISS/TF-IDF (no API key)                 | Put `OPENAI_API_KEY` in a local `.env` if you want LLM synthesis (`HARBORLINE_ANSWER_MODE=llm`) |
| Mock HR tickets / emails (never persist to disk)                                              | A real HarborHub / HRIS write — **not implemented** and must stay mock                          |
| Document architecture in `[docs/mcp.md](docs/mcp.md)`                                         | Start Streamable HTTP yourself if you want that transport instead of stdio                      |




## Prerequisites

- Python 3.11+ (3.12 recommended)
- Optional: Conda, if you prefer `environment.yml`
- Optional: Docker, for the deployment path
- Optional: an OpenAI-compatible API key, read from the environment (never committed)



## Setup



### Virtual environment (venv)

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

Dev extras (pytest):

```powershell
pip install -r requirements-dev.txt
```



### Conda

```powershell
conda env create -f environment.yml
conda activate harborline
pip install -e .
```



### Secrets

Copy the example file and edit the local copy. **Do not commit** `.env`**.**

```powershell
copy .env.example .env
```


| Variable                      | Required                              | Purpose                                                        |
| ----------------------------- | ------------------------------------- | -------------------------------------------------------------- |
| `OPENAI_API_KEY`              | Only for `HARBORLINE_ANSWER_MODE=llm` | Model provider key                                             |
| `OPENAI_MODEL`                | No                                    | Default `gpt-4o-mini`                                          |
| `OPENAI_BASE_URL`             | No                                    | Compatible gateway                                             |
| `HARBORLINE_SEED`             | No                                    | Default `42` for eval sampling and LLM seed                    |
| `HARBORLINE_CHUNK_SIZE`       | No                                    | Deterministic window, default `900`                            |
| `HARBORLINE_CHUNK_OVERLAP`    | No                                    | Deterministic overlap, default `120`                           |
| `HARBORLINE_TOP_K`            | No                                    | Default `5`                                                    |
| `HARBORLINE_ANSWER_MODE`      | No                                    | `retrieve` (default) or `llm`                                  |
| `HARBORLINE_REWRITE`          | No                                    | Query expansion, default `true`                                |
| `HARBORLINE_RERANK`           | No                                    | Lexical + diverse-source rerank, default `true`                |
| `HARBORLINE_FETCH_K`          | No                                    | Candidate pool before rerank, default `20`                     |
| `HARBORLINE_MIN_SCORE`        | No                                    | Guardrail floor, default `0.22`                                |
| `HARBORLINE_RETRIEVE_BACKEND` | No                                    | `faiss` (default) or `tfidf`                                   |
| `HARBORLINE_EMBEDDING_MODEL`  | No                                    | Local MiniLM, default `sentence-transformers/all-MiniLM-L6-v2` |


`.gitignore` excludes `.env`, `.venv/`, and `.cache/`.

## How to execute the RAG pipeline

Do this from the repo root with `.venv` activated. No API key is required.

**1. Parse and clean (markdown, HTML, PDF, TXT)**  
The ingest command reads `corpus/` (and `data/*.json` as structured records). Markdown and HTML are split on headings. PDFs are split by page, then by the same window if a page is long. TXT uses a body window with overlap.

**2–5. Chunk, embed, store, keep citation metadata** — one command:

```powershell
python -m harborline.cli ingest
```

What that does:


| Step     | What runs                                                                     | Why                                                                                    |
| -------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Chunk    | Heading-aware sections, then 900-character windows with 120-character overlap | Policy answers live under `##` headings; overlap keeps a split sentence in both chunks |
| Embed    | Local ONNX **all-MiniLM-L6-v2** via FastEmbed (free, CPU, no API key)         | First run downloads the small model into the FastEmbed cache                           |
| Store    | Persistent **FAISS** index at `.cache/faiss`                                  | Local vector store; cosine similarity (inner product on L2-normalized vectors)         |
| Metadata | `title`, `section`, `source_path`, `source_format`, `snippet`, `kind`, ids    | Citations in `ask` / `--json`                                                          |


You should see counts by format (`md`, `html`, `pdf`, `txt`, `json`) and the FAISS path.

**3. Ask (retrieves from FAISS, prints citations)**

```powershell
python -m harborline.cli ask "How many PTO days do I get after my second anniversary?"
python -m harborline.cli ask "Can I use PTO tomorrow?" --employee-id EMP-1014
python -m harborline.cli ask "What is the US hotel cap?" --json
python -m harborline.cli ask "Should I buy bitcoin with my bonus?"
```

The last example is **out of corpus** and is refused.

**Complex (multi-document) question** — PTO + holidays + hub office days:

```powershell
python -m harborline.cli ask "I live 32 miles from the Seattle office and want PTO Wednesday through Friday of Thanksgiving week 2026. Do I lose PTO hours for the company holidays, and do I still owe three office days that week?"
```

Optional filters: `--kind policy` or `--kind structured`, plus `--source-format md`.

### Generated answers (optional LLM)

Retrieval, rewrite, rerank, citations, and guardrails **do not need an API key**.

To have the model write a **Policy fact / Citations / Not a recommendation** answer:

1. Create an OpenAI account (or any OpenAI-compatible endpoint).
2. Copy `.env.example` to `.env` locally.
3. Set `OPENAI_API_KEY` in `.env` (never commit `.env`, never paste the key into chat).
4. Set `HARBORLINE_ANSWER_MODE=llm`.
5. Run the same `ask` commands. Temperature is `0` and `seed` is `42`.

Azure or a gateway: also set `OPENAI_BASE_URL`.

If you skip ingest, the first `ask` will embed on the fly (slower). Run ingest once.

**Fallback without embeddings:** set `HARBORLINE_RETRIEVE_BACKEND=tfidf` in `.env`.

## Local run (HTTP)

Run ingest first, then:

```powershell
uvicorn harborline.api:app --reload --port 8000
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** for the People Desk chat UI. Use the two grader demo buttons, or POST `/chat`.

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/demos
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"query\":\"Am I eligible for fully remote work living in Tacoma?\",\"employee_id\":\"EMP-1008\"}"
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"query\":\"Can I take PTO next week?\",\"employee_id\":\"EMP-1014\"}"
curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d "{\"query\":\"When does the 401k match vest?\"}"
```

`GET /health` reports `app` plus `mcp.available` and discovered tool names. `POST /chat` runs the MCP orchestrator and returns `answer`, `citations`, `snippets`, and `trace`. `POST /ask` is retrieve-only (no agent).

## Evaluation

Retrieval gold items live in `eval/gold_questions.json` (**recall@k**). The fuller agent/Q&A set is `eval/eval_tasks.json` (26 tasks: policy Q&A, multi-document, tool workflows, ambiguous, out-of-scope) with gold answers.

```powershell
python -m harborline.cli eval
python -m harborline.cli eval --limit 8 --json
python -m harborline.cli report --backend tfidf --write
pytest
```

`report` prints answer quality (groundedness, citation accuracy, partial match), agent behavior (tool selection, workflow completion, escalation/clarification, action safety), latency p50/p95 with a first-task cold vs later warm split, and an ablation (retrieval `top_k` 3/5/8 plus MCP tools vs retrieve-only). `--write` saves `eval/latest_report.json` and `eval/REPORT.md`. Free-tier hosts that sleep add extra cold-start time on the first HTTP hit; the local report notes that separately.

`--limit` samples with `HARBORLINE_SEED` (default 42), so two runs with the same seed and limit return the same subset.

`python -m harborline.cli eval` uses FAISS after ingest. `pytest` uses TF-IDF so unit tests stay offline and fast.

Heading-aware chunking is deterministic. Oversize sections use a fixed window (no shuffle). `PYTHONHASHSEED` is set when you call `Settings.apply_seeds()`.

## Deployment

The image serves FastAPI. Pass secrets at **runtime**; do not bake keys into the image.

```powershell
docker build -t harborline-qa .
docker run --rm -p 8000:8000 --env-file .env harborline-qa
```

Or inject a single key:

```powershell
docker run --rm -p 8000:8000 -e HARBORLINE_ANSWER_MODE=retrieve harborline-qa
```

Health check: `GET /health`.  
Ask: `POST /ask`.  
Eval: `GET /eval`.

For a hosted deploy (Cloud Run, App Service, Fly.io, Render), set the same env vars in the service configuration, attach `corpus/`, `data/`, and `eval/`, and keep `HARBORLINE_SEED=42` if you want eval numbers that match local runs.

## CI / CD

`[.github/workflows/ci.yml](.github/workflows/ci.yml)` runs on every **push** and **pull request**.

1. Install `requirements.txt` + `requirements-dev.txt` and `pip install -e .`.
2. Import/start check: load `harborline.api:app` and the MCP server factory.
3. `pytest` including:
  - **App start:** `GET /` and `GET /health` (`tests/test_api.py`)
  - **MCP discovery + call:** `mcp.discovered_tools` on `/health`, plus `tests/test_mcp.py` (`tools/list` and `lookup_employee_profile`)
4. **Deploy runs only if that test job succeeds** (`needs: test`). Pull requests never deploy. On push, CI calls a Render deploy hook **only** if you add a GitHub Actions secret named `RENDER_DEPLOY_HOOK`. Until that secret exists, the deploy job is a successful no-op (no live URL yet).

CI uses `HARBORLINE_RETRIEVE_BACKEND=tfidf` so it stays offline and does not download MiniLM.

## Reproducibility


| Knob                                | Default              | Effect                                     |
| ----------------------------------- | -------------------- | ------------------------------------------ |
| `HARBORLINE_SEED`                   | 42                   | `random`, NumPy, eval sampling, LLM `seed` |
| `HARBORLINE_CHUNK_SIZE` / `OVERLAP` | 900 / 120            | Same text always yields the same chunks    |
| FAISS + MiniLM                      | local ONNX FastEmbed | Persistent vectors in `.cache/faiss`       |
| TF-IDF retrieve                     | optional             | Stable sort: score desc, `chunk_id` asc    |




## Tools and MCP

Full write-up: `[docs/mcp.md](docs/mcp.md)`.

The MCP server is `python -m harborline.mcp_server` (FastMCP, **stdio** by default). `.cursor/mcp.json` points Cursor at this repo's venv Python. The agent client (`harborline.mcp_client`) **discovers** tools with `tools/list` and **calls** them with `tools/call`. Hard-coded `harborline.tools` imports are not used during agent execution.

**RAG / policy evidence:** `search_policy_documents`, `get_policy_section`, `check_policy_compliance`  
**Mock HarborHub rows:** `lookup_employee_profile`, `check_pto_balance`, `lookup_benefits_status`  
**Mock operations:** `create_mock_hr_ticket`, `draft_hr_email` (never persist; `--confirm` is session-only)

```powershell
python -m harborline.cli mcp-probe --transport mcp-stdio --backend tfidf
python -m harborline.cli tool lookup_employee_profile EMP-1008
python -m harborline.cli tool search_policy_documents "PTO carryover 40 hours" --kind policy --backend tfidf
python -m harborline.cli tool get_policy_section POL-PTO-001 --section Eligibility
python -m harborline.cli tool create_mock_hr_ticket --topic pto_request --employee-id EMP-1008 --summary "Friday off"
```

`--confirm` only stores a **session-only MOCK** id. Nothing is written to `data/tickets.json` or any live HRIS.

Optional localhost MCP (EXTERNAL: you start this process):

```powershell
python -m harborline.mcp_server --transport streamable-http --port 8765
```



### EXTERNAL — enable MCP in Cursor (this chat cannot do this)

1. Install deps so the `mcp` package is present (`pip install -r requirements.txt` and `pip install -e .`).
2. Confirm `.cursor/mcp.json` exists (already in the repo).
3. **You** enable MCP in **Cursor Settings** and allow the `harborline` server.
4. **You** restart Cursor after editing `mcp.json`.
5. For FAISS inside the Cursor-hosted server, **you** run ingest once (or set `HARBORLINE_RETRIEVE_BACKEND=tfidf` in `mcp.json`).
6. Optional LLM synthesis: **you** put `OPENAI_API_KEY` in a local `.env` (never commit it) and set `HARBORLINE_ANSWER_MODE=llm`.
7. Streamable HTTP is not started by Cursor unless **you** launch it and add the URL.

The CLI agent does **not** need Cursor Settings. Default transport is stdio (`python -m harborline.cli agent`). Use `--transport mcp-inproc` to stay in one process.

## Agent orchestrator

`python -m harborline.cli agent` interprets intent, decides whether RAG alone is enough, calls **MCP-exposed** tools, and prints a **visible operational trace** (discovered tools, selected tools, arguments, output summaries, retrieved sources, escalation). This is a log, not hidden chain-of-thought.

Two multi-step HR workflows are wired end-to-end:


| Workflow                | Example                                                    | MCP tools                                                                                               |
| ----------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Remote work eligibility | EMP-1008 lives in Tacoma (32 miles) and is still coded hub | `lookup_employee_profile`, `search_policy_documents`, `check_policy_compliance`                         |
| PTO request guidance    | EMP-1014 is not eligible to use PTO until 2026-10-08       | `lookup_employee_profile`, `check_pto_balance`, `get_policy_section`; submit is `create_mock_hr_ticket` |


Also routed: benefits (`lookup_benefits_status`), expense compliance, onboarding (`get_policy_section`), and HR case triage (ticket + email are MOCK).

```powershell
# Default: spawn the MCP stdio server, then tools/list + tools/call. No API key.
python -m harborline.cli agent "Am I eligible for fully remote work living in Tacoma?" --employee-id EMP-1008 --backend tfidf
python -m harborline.cli agent "Can I take PTO next week?" --employee-id EMP-1014 --backend tfidf
python -m harborline.cli agent "Can I take PTO next week?" --employee-id EMP-1014 --backend tfidf --transport mcp-inproc
```

Graceful failures: missing employee ids, incomplete policy evidence, ambiguous requests, and an unavailable MCP bus. Irreversible actions stay MOCK unless you pass `--confirm`, and even then they never persist to disk.

## Project layout

```
corpus/             Policy documents (md, html, txt, pdf)
data/               Mock employees, PTO, benefits, tickets
eval/               Gold questions
harborline/         Parse, chunk, embed, FAISS, ask, tools, MCP server/client, agent, API
docs/mcp.md         MCP transport, schemas, discovery
.cursor/mcp.json    Cursor MCP server config (you still enable MCP in Settings)
scripts/            PDF builder for companion policy sheets
tests/              Determinism, eval, tools, and orchestrator tests
requirements.txt    Pip pins
requirements-dev.txt
environment.yml     Conda env
pyproject.toml      Package metadata
.env.example        Secret names only
Dockerfile
```




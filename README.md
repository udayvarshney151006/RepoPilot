# RepoPilot

**Understand, debug and navigate a codebase with repository evidence.**

RepoPilot is a codebase intelligence platform with code-aware indexing, hybrid
retrieval, cited answers, an import graph, a constrained debugging agent, and
measured retrieval evaluations. It combines a Next.js developer workspace with a
FastAPI backend and a PostgreSQL/pgvector deployment.

The application works without an API key. That mode uses **local feature-hash
vectors and extractive source summaries**. It demonstrates the full retrieval
and approval pipeline, but does not provide a neural semantic embedding model
or a general autonomous coding model. External generation and embedding
providers are configured separately. This is a trusted, single-user MVP.

## Demo

Captured from the running local application, using the bundled repository and
offline providers:

![RepoPilot landing page](docs/screenshots/landing.png)

![Repository answers and retrieval inspector](docs/screenshots/workspace.png)

[Evaluation dashboard with an executed run](docs/screenshots/evaluations.png) ·
[Agent trace, unavailable sandbox results and staged diff](docs/screenshots/agent.png) ·
[Impact answer with cited import evidence](docs/screenshots/impact.png)

1. Open `http://localhost:3000` and connect the bundled **Tiny Shop** demo.
2. Watch ingestion progress through queued, cloning, parsing, embedding and
   indexing to ready.
3. Ask **“Where is JWT token signature and expiration validation implemented?”**
   Open the `shop/auth.py` citation to inspect the source and line range.
4. Browse files and inspect the dependency graph. `shop/routes.py` imports both
   authentication and checkout code. Ask “If I change `validate_token`, which
   files may be affected?” to inspect the cited import chains in Ask Repo.
5. Open Evaluations and run the bundled cases. The dashboard compares vector,
   BM25, hybrid and hybrid with reranking using the results of that run.
6. Ask the agent: **“POST /checkout returns 500 when an item omits quantity.
   Find the cause and propose a tested fix.”** Inspect its tools and proposed
   diff. Approve or reject the patch.

The demo has a real regression: `calculate_total` indexes `item['quantity']`
despite quantity being optional. Its regression test fails before repair.
Approval changes RepoPilot's managed copy, preserving the bundled original.
Sandbox output explicitly says unavailable when Docker execution cannot run;
that state does not mean tests passed.

## Features

- Public GitHub import, bounded ZIP upload and a bundled demonstration repository.
- Background indexing with persistent status and errors.
- Python, JavaScript and TypeScript symbols, code-aware chunks and source ranges.
- Independent embedding, generation and reranking provider boundaries.
- Explicit upload, file, chunk and context budgets with indexing notices for skipped source.
- BM25, cosine vector retrieval, reciprocal rank fusion and heuristic reranking.
- Persisted per-repository lexical statistics with a bounded in-memory corpus cache.
- Repository-grounded answers, clickable citations and retrieval/timing inspection.
- File explorer, conservative import relationships and reverse-dependency impact.
- Validated agent tools, action traces, bounded execution and source-backed patches.
- Human approval with original-content checks before applying a staged diff.
- Docker sandbox interface with resource/time limits and honest unavailable status.
- Real four-strategy evaluation runs with persisted ranking and answer proxy metrics.
- PostgreSQL/pgvector, Redis/RQ deployment and an explicit SQLite/local-job fallback.
- Responsive workspace, theme control, code highlighting and unified diff display.

## Architecture

```mermaid
flowchart TD
    UI[Next.js workspace] --> API[FastAPI API]
    API --> DB[(PostgreSQL + pgvector)]
    API --> Queue[(Redis / RQ)]
    Queue --> Worker[Background worker]
    Worker --> Intake[Validate GitHub / ZIP / demo]
    Intake --> Parse[Tree-sitter + semantic chunks]
    Parse --> Embed[Embedding provider]
    Embed --> DB
    API --> Retrieve[BM25 + vector retrieval]
    Retrieve --> Fusion[Reciprocal rank fusion]
    Fusion --> Rank[Reranker]
    Rank --> Answer[Grounded generator + citations]
    Answer --> UI
    Worker --> Agent[Bounded agent tools]
    Agent --> Sandbox[Disposable Docker sandbox]
    Agent --> Patch[Staged patch + trace]
    Patch --> Approval[Human approval]
    Approval --> Intake
    Worker --> Eval[Executed evaluations]
    Eval --> DB
```

SQLite stores vectors as JSON and local jobs use an in-process executor for a
simple laptop demo. PostgreSQL stores native pgvector vectors; Redis serves RQ
jobs and optional query-result caching. These are explicit operating modes, not
equivalent scaling guarantees. See [architecture](docs/architecture.md).

## How RAG works

Ingestion extracts functions, classes and source ranges instead of sending an
entire repository to a model. At query time, BM25 finds exact identifiers while
vector retrieval ranks representations of code. Reciprocal rank fusion merges
their rankings, and a reranker favors relevant code and symbol matches. The
generator receives a bounded context and returns citations tied to retrieved
chunks. A source click opens the indexed file at the cited lines.

Ingestion persists BM25 term/document statistics in a repository-scoped JSON
index. Queries reuse a matching index generation through a bounded cache;
missing or invalid artifacts rebuild from indexed evidence. Query scoring still
uses the repository corpus and is intended for small repositories.

The offline embedding provider hashes tokens into a fixed-size normalized
vector. This is a deterministic baseline with vocabulary overlap, **not learned
semantic understanding**. The fallback reranker is an identifier-aware heuristic,
not a cross-encoder. API-key-backed generation and embeddings can be enabled
without changing ingestion or UI. See [RAG design](docs/rag.md).

## Agent architecture

The agent records explicit search, file, symbol, reference, dependency, test and
patch actions. Tool arguments are validated, steps are capped, and commands use
an allowlist. Its trace exposes useful action summaries and tool outputs.

The offline planner supports the reproducible checkout fix and evidence-based
investigation; it is intentionally limited. Patches are prepared in an isolated
copy, displayed as unified diffs, and checked against original source hashes.
Approval applies the staged changes to the managed repository and refreshes its
index. Rejection leaves source untouched. See [agent design](docs/agent.md).

## Dependency analysis

The graph shows conservatively resolved file imports. Selecting a file reveals
its incoming and outgoing edges; impact follows reverse imports. Ask Repo also
uses this traversal for questions such as “If I change `calculate_total`, which
files may be affected?” It resolves an explicitly named file or unique symbol,
adds target/importer source citations and explains the potential import chains.
Ambiguous targets ask for a unique path instead of guessing. Dynamic imports,
aliases and framework dispatch limit coverage; file imports do not prove that
a particular function is called. See
[architecture](docs/architecture.md#dependency-analysis).

## Sandbox security

Repository tests run only through a disposable Docker container. The runner
uses a filtered source snapshot, no network, a read-only container root,
unprivileged execution, dropped capabilities, process/CPU/memory limits, bounded
output and a timeout. It never executes untrusted tests on the API host.

The default Compose deployment **does not mount the Docker socket** and reports
sandbox execution unavailable. To demonstrate sandbox execution, run the backend
on the host with Docker installed, build the test image and opt in as described
below. A Docker daemon is a privileged capability; production needs an isolated
runner service. See [security](docs/security.md).

## Evaluation

The demo dataset specifies a question, expected source file, expected symbol and
answer keywords. Every evaluation executes four retrieval strategies and stores
Recall@K, MRR, latency, retrieved count, keyword coverage and citation validity.
Tokens/cost appear only when the provider reports usage and pricing is configured.

Keyword coverage and citation validity are transparent proxies. They do not
prove semantic correctness or entailment. No benchmark values are populated
before a run. Small demo results must not be presented as production accuracy.
See [evaluation methodology](docs/evaluation.md) and the actual
[saved demo evaluation](docs/demo-evaluation-run.json).

## Tech stack

| Layer | Technology |
| --- | --- |
| Workspace | Next.js, React, TypeScript, Tailwind CSS, Prism |
| API and schemas | FastAPI, Pydantic |
| Persistence | SQLAlchemy, Alembic, PostgreSQL, pgvector |
| Local fallback | SQLite, JSON vectors, in-process jobs |
| Parsing | Tree-sitter Python/JavaScript/TypeScript grammars |
| Retrieval | BM25, cosine similarity, reciprocal rank fusion |
| Jobs and cache | Redis, RQ |
| Execution | Docker sandbox with validated commands |
| Verification | pytest, TypeScript checks, production build, Playwright |

## Local setup

Prerequisites: Python 3.12+, Node.js 22 with Corepack, Git. Docker with Compose
is required for the PostgreSQL deployment and optional test sandbox. Start from
the repository root. Provider keys are optional.

### Option A: Docker Compose

PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

macOS/Linux:

```sh
cp .env.example .env
docker compose up --build
```

Compose starts PostgreSQL/pgvector, Redis, the API, a worker and Next.js, with
health checks. The API runs Alembic before serving requests. Browser access is
`http://localhost:3000`; OpenAPI is `http://localhost:8000/docs` and health is
`http://localhost:8000/api/health`. Ports are bound to loopback.

```sh
docker compose ps
docker compose logs -f backend worker
docker compose down
```

Named volumes preserve database, Redis and repository data. Removing volumes
deletes that local state. The Docker stack is provided for environments with a
working daemon; it must be verified on such a machine before claiming it ran.

### Option B: local SQLite, no Docker or API key

PowerShell, terminal 1:

```powershell
.\scripts\setup-local.ps1
.\scripts\start-backend.ps1
```

PowerShell, terminal 2:

```powershell
.\scripts\start-frontend.ps1
```

macOS/Linux, terminal 1:

```sh
sh scripts/setup-local.sh
sh scripts/start-backend.sh
```

macOS/Linux, terminal 2:

```sh
sh scripts/start-frontend.sh
```

The setup creates an isolated `.venv`, installs the backend/frontend, copies
`.env.example` only when `.env` is absent and applies migrations. Defaults are
SQLite, local jobs, feature-hash embeddings and offline generation. If `.env`
already points at PostgreSQL/RQ, those services must be running.

Backend installations use [tested dependency constraints](backend/requirements.lock.txt);
the frontend uses its pnpm lockfile. The Python constraints capture the verified
Windows environment and pin matching requirements. Platform-specific optional
dependencies, such as Linux uvloop, are resolved on the target platform.

### Enable real Docker sandbox tests

Use the **host backend**, with a working Docker daemon:

```sh
docker build -f backend/Dockerfile.sandbox -t repopilot-sandbox:local .
```

Set `SANDBOX_ENABLED=true` in `.env` and restart the backend. The image has pytest
preinstalled; sandbox network access remains disabled. Retry the demo agent to
see baseline failure and candidate test output. The npm allowlist does not
install dependencies at runtime. Set `SANDBOX_NODE_IMAGE` to a locally available
image with the JavaScript project's test dependencies preinstalled; its default,
`node:22-alpine`, supplies Node/npm only. Images are never pulled during test
execution. Custom images must expose tools/modules from outside `/workspace`,
whose temporary mount hides image files at that path. Image launch failures are
reported.

To use PostgreSQL/RQ while the backend runs on the host:

```sh
docker compose up -d postgres redis
```

Then set `DATABASE_URL=postgresql+psycopg://repopilot:repopilot-local-password@localhost:5432/repopilot`,
`REDIS_URL=redis://localhost:6379/0`, and `JOB_BACKEND=rq`. Run migrations, start
the API and run `python -m app.worker` from `backend` in a separate activated
virtual-environment terminal.

### Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
corepack pnpm typecheck
corepack pnpm build
corepack pnpm exec playwright install chromium
corepack pnpm test:e2e
```

Playwright uses the running frontend at port 3000 and API at port 8000. Keep the
two local startup terminals running before the browser test. The separate
`demo-repository/tests` suite deliberately
contains a failing regression; it is not part of RepoPilot's passing unit suite.
Developer verification of the trusted bundled source observed **6 passing tests
and 1 failing checkout regression**; the same seven tests passed in a temporary
copy after the quantity-default change. This was host-side verification of code
authored for the demo, not an application sandbox run. Docker execution remains
unverified on the development machine.
Verified results and environment limitations are recorded in
[validation record](docs/validation.md) and [development log](docs/development-log.md).

The CI workflow checks backend behavior/migrations and frontend typing/build,
then starts the real API and Next.js for the Playwright happy path. It uses the
offline/local mode and explicitly disables Docker execution for that browser
check; no API responses are mocked.

## Environment variables

See [.env.example](.env.example). Never commit `.env` or expose provider keys to
the browser. Restart processes after configuration changes. Next.js uses a
server-side runtime proxy configured in `frontend/.env.local` for local startup;
Compose supplies its internal API target automatically.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLite development or PostgreSQL/psycopg connection |
| `DATA_DIR` | Managed repository copies |
| `JOB_BACKEND` | `local` executor or `rq` worker |
| `REDIS_URL` | RQ broker and optional query cache |
| `LLM_PROVIDER` | `extractive` offline summaries or `openai` generation |
| `EMBEDDING_PROVIDER` | `local` hashing or `openai` embeddings |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Server-only API configuration |
| `LLM_MODEL`, `EMBEDDING_MODEL` | Independently selected model IDs |
| `EMBEDDING_DIMENSIONS` | Fixed at 384 for the MVP schema/provider configuration |
| `QUERY_CACHE_TTL` | Short query cache lifetime |
| `LLM_INPUT_COST_PER_MILLION`, `LLM_OUTPUT_COST_PER_MILLION` | Optional generation pricing in USD per million tokens |
| `CORS_ORIGINS` | Allowed development origins |
| `API_AUTH_TOKEN` | Optional API bearer token; see deployment limitations |
| `SANDBOX_ENABLED`, `SANDBOX_IMAGE`, `SANDBOX_TIMEOUT` | Opt-in runner settings |
| `AGENT_MAX_STEPS` | Upper bound on an agent run |
| `SERVER_API_URL` | Next.js server proxy target, without `/api` |
| `SERVER_API_AUTH_TOKEN` | Server-only token in `frontend/.env.local`, matching backend `API_AUTH_TOKEN` when enabled |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose development DB |

Changing embedding provider/model requires reindexing repositories. The current
schema fixes vectors at 384 dimensions; supporting another size needs a migration
and compatible provider configuration.
Sending repository evidence to a hosted provider is a deliberate configuration
choice; inspect your repository for secrets first.

## API documentation

FastAPI's live [Swagger UI](http://localhost:8000/docs) is authoritative for
request/response validation. Routes use the `/api` prefix; key operations are:

```text
POST /api/repositories                  import public GitHub URL
POST /api/repositories/demo             add bundled demo
POST /api/repositories/upload           upload ZIP
GET  /api/repositories/{id}/status      indexing progress
POST /api/repositories/{id}/query       question and retrieval strategy
GET  /api/repositories/{id}/files       source browser
GET  /api/repositories/{id}/dependencies import graph
GET  /api/repositories/{id}/impact      reverse-import impact
POST /api/repositories/{id}/agent-runs  investigate task
POST /api/agent-runs/{id}/approve       apply staged patch
POST /api/agent-runs/{id}/reject        reject staged patch
POST /api/repositories/{id}/evaluations execute comparisons
GET  /api/evaluations/{id}              measured results
```

## Engineering decisions

| Decision | Reason and cost |
| --- | --- |
| RAG instead of whole-repo prompts | Bounds model context and returns inspectable evidence; retrieval can miss necessary context. |
| Hybrid search | Exact identifiers and semantic queries need different signals; two candidate searches add work. |
| Reranking | Improves the evidence shortlist; the local heuristic is cheap but less expressive than a trained model. |
| Code-aware chunks | Preserves meaningful symbols and citation ranges; large functions still need bounded fragments. |
| pgvector | Keeps metadata and vectors in one transactional database with a PostgreSQL HNSW index; approximate search needs recall/latency tuning under load. |
| Human approval | A visible diff and content checks protect managed source; people still need to assess a patch. |
| Docker execution | Separates untrusted test code from the API process; daemon provisioning and stronger isolation remain operational concerns. |
| Background jobs | Keeps indexing/agent/evaluation work off request threads; workers need monitoring and retry policy. |
| Offline fallback | Supports a reproducible no-key demo; feature hashing and extraction cannot replace neural models. |

## Limitations and future improvements

This MVP is for a trusted local user, with no production account/tenant
authorization. An optional shared API token is not multi-user access control;
the Next server can forward it without exposing it to browser JavaScript. The
frontend still assumes a trusted local user and has no end-user login.
Do not publish the default deployment directly to the internet.

File import edges are approximate. Offline answers and patch planning are
limited. Full-corpus lexical scoring and the local vector fallback suit small
repositories. Local
jobs are lost if the process exits. Docker availability, model calls and network
imports can fail, with explicit error states. Prompt boundaries and filters
reduce risk but do not guarantee that a hosted model will resist every attack.

Default admission limits are 25 MiB for ZIP/downloads, 64 MiB expanded source,
512 KiB per file, 2,000 files and 10,000 chunks. Chunks contain at most 100 lines
and 6,000 UTF-8 bytes; selected answer context is capped at 30,000 characters.
An oversized source line causes that file to be skipped with an indexing notice,
so a ready repository can have explicit coverage gaps.

Next improvements: authenticated tenant isolation, commit-aware incremental
indexing, trained local embeddings/cross-encoder reranking, vector-index tuning
measured against recall, richer dependency resolution, durable retry
and cancellation, and a remote sandbox service with stronger isolation.

## Explain it in interviews

- [Architecture and component tradeoffs](docs/architecture.md)
- [Retrieval and grounding](docs/rag.md)
- [Agent, tools and approval](docs/agent.md)
- [Threat model and sandbox](docs/security.md)
- [Evaluation definitions and limitations](docs/evaluation.md)
- [30-second, 1-minute, 2-minute explanations and questions](docs/interview-guide.md)
- [Three honest resume bullets](docs/resume.md)

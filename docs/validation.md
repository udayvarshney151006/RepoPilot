# Validation record

These results were observed during local development on **1 October 2026
(Asia/Calcutta)**. They describe this workspace and the small datasets below;
they are not production capacity, accuracy or latency guarantees.

## Environment and operating mode

- Windows host, isolated Python virtual environment and Node runtime.
- SQLite persistence, JSON vectors and local background jobs.
- `local-feature-hash-v1:384` embeddings, `extractive-offline` generation and the
  identifier-aware heuristic reranker.
- Live FastAPI API on port 8000 and Next.js workspace on port 3000.
- Chromium integration against real services; no API responses mocked.

Backend versions are captured in
[requirements.lock.txt](../backend/requirements.lock.txt). Setup, Docker and CI
use this file as pip constraints. It records the tested Windows environment
rather than every platform's complete dependency closure; optional Linux
dependencies such as uvloop remain target-platform resolutions. The frontend
uses its checked-in pnpm lockfile.

## Executed checks

| Check | Observed result | Scope |
| --- | --- | --- |
| Backend pytest | 110 passed, 1 skipped in 13.02 s | API, ingestion, parsing, persisted lexical indexing, ranking, budgets, security, tools, patches and evaluations |
| Ruff | Passed | Backend application and tests |
| Alembic | All three migrations applied; `check` reported no pending operations | SQLite schema and migration behavior |
| Frontend type check | Passed | TypeScript and server proxy |
| Frontend production build | Passed, 12 routes generated | Next.js route compilation |
| Chromium integration | 3 tests passed | Repository workflow, mobile navigation and real ZIP upload through the proxy |
| Compose configuration | `docker compose config --quiet` passed | Configuration only; containers were not started |
| PowerShell scripts | Syntax parser checks passed | Local setup/start scripts |
| Docs and dataset | Links resolved; six expected symbols parsed | Documentation and Python/JS/TS evaluation identity |

The skipped test requires Windows symlink-creation privilege unavailable to the
process. The warning is an upstream Starlette deprecation warning. Neither is
hidden as a clean all-platform result. Linux CI is configured for tests,
migrations, lint and a real browser flow; local checks do not prove a remote
CI run completed.

The browser workflow imported the demo, waited for indexing, asked a question,
opened source citations/retrieval inspection, browsed files, selected graph
nodes, ran an evaluation and rejected an agent patch. The ZIP case sent a real
archive through the Next.js proxy. The final three-test browser run also verified
responsive theme persistence and completed in **36.1 seconds** in this environment.

## Live ingestion and source evidence

Tiny Shop indexed **11 files and 31 chunks** after excluding `evaluation.json`
from the retrieval corpus. The metadata remains browseable but cannot become
evidence for its own questions.

A real GitHub import of [pallets/itsdangerous](https://github.com/pallets/itsdangerous)
indexed **29 files and 185 chunks**. Queries retrieved the `Signer` class and its
methods from that imported source. This verifies another repository's import
and evidence path, not broad retrieval accuracy.

The trusted authored shop was also verified separately on the host: baseline
**6 passed / 1 intentional `KeyError: 'quantity'` failure**; a temporary candidate
with `item.get('quantity', 1)` had **7 passed**. These developer checks were not
Docker executions and do not change the agent's unavailable test results.

## Saved evaluation provenance

The actual API response is [demo-evaluation-run.json](demo-evaluation-run.json):

- Run ID: `bf264272-d5f8-4235-80f1-905ff39c7042`.
- Repository ID: `63f75aff-b8a7-43f2-b3fb-fda47c48f760`, a managed demo copy.
- Created: `2026-09-30T21:31:15.978352+00:00`, corresponding to **1 October 2026,
  03:01:15 IST**.
- K=5, six authored cases, four strategies and 24 executed case results.
- SQLite/local jobs, feature-hash vectors, extractive answers and heuristic reranking.
- Token usage and estimated cost are null because they were unavailable.

| Strategy | Recall@5 | MRR | Mean retrieval + generation latency |
| --- | --- | --- | --- |
| Vector baseline | 1.000000 | 0.888889 | 8.07 ms |
| BM25 | 1.000000 | 0.916667 | 7.57 ms |
| Hybrid | 1.000000 | 1.000000 | 11.45 ms |
| Hybrid + reranker | 1.000000 | 1.000000 | 11.69 ms |

Recorded keyword-coverage and citation-validity proxies were 1.0 for these cases.
A keyword hit or real citation does not prove semantic correctness. This small,
identifier-rich dataset is authored alongside its source and favors lexical
matching. Timings are single local observations, not promises for larger repos,
hosted providers, PostgreSQL or concurrent users. See [methodology](evaluation.md).
The saved run precedes the final persisted-lexical-index integration; its timings
describe that recorded run and are not evidence of cache improvement or the final
version's query latency. Re-run before comparing the new lexical path.

## Budgets and failure behavior

Defaults are 25 MiB ZIP/downloads, 64 MiB expanded source, 512 KiB per file,
2,000 indexed files and 10,000 chunks. Each code chunk has at most 100 lines
and 6,000 UTF-8 bytes. Selected source/path/symbol answer context is capped at
30,000 characters; serialized metadata and the question add overhead. Oversized
source lines cause a file to be skipped with visible notices, preserving complete
source-line citations instead of silently truncating them.

Tests cover unsafe paths/archives, commands, unapproved-source preservation,
stale patch conflicts, source/citation matching, provider-change invalidation,
byte/line/context budgets and honest unavailable sandbox results. Empty-evidence
generation refuses to invent a source-backed answer, and external generation
with invalid citation IDs is rejected. Queue admission uses JSON payloads and
API timestamps carry explicit UTC offsets.

The lexical layer persists per-repository JSON term/document statistics bound to
chunk IDs and index generation, with a bounded memory cache. It reuses those
statistics instead of tokenizing each full corpus on every query.

## Unverified paths

Docker CLI was installed, but its daemon remained unavailable, including an
attempted Docker Desktop startup. **No PostgreSQL/pgvector, Redis/RQ deployment
or Docker sandbox execution was verified here.** Configuration and sandbox
control tests do not establish that containers or repository tests ran.

Hosted inference is implemented behind provider interfaces and checked at its
contracts; live calls were not verified without an API key. Hostile-tenant Docker
containment, public multi-user authorization, 10,000-repository capacity and
production load remain outside this evidence.

## Reproduce

Use README setup and keep the API/frontend running for browser tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m ruff check backend\app backend\tests
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic check
Set-Location ..\frontend
corepack pnpm typecheck
corepack pnpm build
corepack pnpm exec playwright install chromium
corepack pnpm test:e2e
```

Run a new evaluation in the UI against the ready demo rather than seeding its
database with the saved response. Fix operating mode, source and dataset when
comparing retrieval changes.

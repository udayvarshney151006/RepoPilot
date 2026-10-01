# Development and validation log

## Planning

- Empty workspace inspected and specification decomposed into nine phases.
- Architecture, file ownership, API contract and environment constraints recorded before code.
- Node 24 and bundled Python available. Docker CLI installed; daemon unavailable (named pipe missing).
- PostgreSQL/Redis path plus explicit SQLite/local-job development fallback selected.

Subsequent phase results will be recorded after execution, including failures and limitations.

## Phases 1–4: foundation, ingestion, RAG and intelligence

- FastAPI launched on localhost:8000; real health and OpenAPI endpoints served.
- Alembic migrations applied to SQLite and schema comparison reports no pending differences. Required-field migration preserves referencing rows during SQLite batch recreation.
- Bundled demo indexed via an HTTP background job: 11 files; initially 32 chunks. Validation discovered ground-truth evaluation data entering search, which was fixed by excluding evaluation.json from chunks and both retrieval paths.
- Python/JavaScript/TypeScript Tree-sitter symbol extraction, module coverage, bounded oversized functions, BM25 length normalization, RRF, reranking and citation line/content equality verified.
- Dependency traversal finds shop/routes.py and tests/test_auth.py affected by shop/auth.py changes.
- GitHub URL/ZIP/path validation, Windows reserved paths, redaction with preserved line count and provider-change invalidation covered.
- Backend suite at this checkpoint: 66 passed, 1 skipped (Windows symlink creation privilege unavailable).

## Phases 5–7: agent, sandbox and evaluation

- Typed tool schemas, bounded offline investigation and configured-provider tool loop implemented.
- Staged checkout fix preserves source before approval; tests cover reject, approve, stale hashes, invalid paths, command restrictions and restricted container arguments.
- Docker-unavailable results say executed=false and carry no fabricated exit code.
- Real four-strategy evaluation persists retrieval, keyword coverage and citation validity metrics. Answer assessment proxies are explicitly labeled; unknown token/cost values remain null.
- Trusted authored demo developer verification: baseline 6 passed / 1 intentional failure; separately patched temporary candidate 7 passed. These are host developer checks, not Docker sandbox results.

## Phase 8: application verification and hardening

- Actual public GitHub import of pallets/itsdangerous completed: 29 supported files, 185 chunks; Signer and signature methods retrieved with actual line ranges.
- API integration covers queries/conversations, ZIP import, staged rejection, approval and reindexing, conflict responses, actual evaluations, auth/rate limits, queue failures and unsafe/oversized inputs.
- Pre-parser Content-Length limits prevent oversized multipart spooling. The Next server proxy forwards bounded upload lengths; actual browser ZIP import passed.
- Added byte/line/context/chunk budgets, explicit skipped-file warnings, no-evidence refusal, rejection of invalid model citation IDs, external-vector normalization and UTC serialization.
- Repository admission uses local locks and PostgreSQL row locks; index/approval waits for active agent/evaluation work to avoid mixing index generations.
- Final checkpoint: 96 backend tests passed, one Windows symlink privilege skip; Ruff passed. Upstream Starlette TestClient emitted one deprecation warning.
- All three Alembic migrations applied; schema comparison reports no pending operations.
- Production Next.js build and TypeScript passed (12 routes). Three real-API Chromium tests passed, including responsive theme persistence, actual ZIP ingestion and the full code intelligence flow. Screenshots captured in docs/screenshots.
- Real six-case/four-strategy evaluation saved in docs/demo-evaluation-run.json. Results are limited to the offline authored demo and are not a general accuracy claim.
- Browser inspection independently verified the landing/dashboard, an authentication question and a cited source viewer highlighting lines 53–67.
- Installed Docker Desktop was started in the background, but the daemon remained unreachable. PostgreSQL/Redis container execution, sandbox execution and hosted AI requests remain unverified in this environment.

## Phase 9: documentation and handoff

- README includes actual screenshots, setup commands, configuration, architecture diagram and honest limitations.
- Architecture, RAG, agent, security and evaluation design documents include alternatives, tradeoffs and scale considerations.
- Interview guide includes natural 30-second, 1-minute and 2-minute explanations and topic questions; resume bullets use implemented features.
- Recorded dependencies, CI checks, Compose configuration and local startup scripts are included. Credentials and runtime data are ignored by Git.

## Final lexical-index verification

- Ingestion now builds a persisted BM25 corpus with term counts, document frequency and lengths, written atomically per repository/index generation.
- Query lookup uses a bounded memory cache and the saved corpus rather than tokenizing source on every request. Missing, stale or corrupt artifacts rebuild from indexed, redacted chunks.
- Fourteen focused tests verify score equivalence, exact chunk/generation validation, disk/cache bounds, corruption recovery and query-only tokenization.
- Final consolidated backend result: 110 passed, one Windows symlink privilege skip; Ruff passed. The recorded six-case evaluation above predates persistence and uses the same BM25 scoring formula.
- Live API verification reindexed the original demo to 11 files and 31 chunks, wrote a 13,554-byte lexical artifact, and retrieved the actual `validate_token` source at lines 53–67. Both application health checks returned HTTP 200 after the final restart.
- Final handoff inspected committed files, setup consistency and credential/runtime exclusions. An isolated source copy passed TypeScript without generated `.next` files, confirming the configured CI type-check order. No frontend code change was needed.

## Continued requirements audit

- Preserved the completed implementation and audited the original specification against the recorded local commit. Found and completed three integration gaps: configurable prebuilt JavaScript sandbox images, shared request IDs through the proxy/API/query logs, and graph traversal plus source retrieval for natural-language impact questions.
- Impact questions resolve explicit file paths, unique basenames or exact symbols. Ambiguous and missing targets request clarification without calling a generation provider; source evidence remains within the existing chunk/context budgets. Reverse-import chains describe potential impact and retain static-analysis limitations.
- Consolidated regression checks passed: 136 backend tests in 10.39 seconds, one Windows symlink privilege skip, Ruff and Alembic schema comparison. The final citation regression retains the named target and import chunks ahead of incidental same-file matches, even without generated citations.
- Frontend TypeScript and the production build passed after the proxy change. Three actual-API Chromium flows passed in 32.5 seconds; a separate new impact/citation/request-ID browser case passed in 7.3 seconds. A live proxy query independently matched its response ID to both HTTP and query logs. Updated screenshots include the real impact answer.

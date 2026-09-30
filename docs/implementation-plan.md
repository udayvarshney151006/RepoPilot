# RepoPilot implementation plan

## Architecture and boundaries

Next.js App Router / TypeScript / Tailwind calls a versioned FastAPI REST API. SQLAlchemy stores repositories, files, semantic chunks, conversations, jobs, agent traces, patches and evaluation records. PostgreSQL + pgvector is the primary deployment; SQLite + JSON vectors is an explicit single-developer fallback. Redis/RQ separates API requests from indexing, agent and evaluation workers; an in-process executor is available for local demonstration. Providers for embeddings, generation, reranking and sandbox execution are independent.

Ingestion validates a public GitHub URL or bounded ZIP, stages a private working copy, filters files and secrets, parses Python/JS/TS with Tree-sitter, embeds code-aware chunks and records conservative import relationships. Retrieval uses BM25 and cosine similarity, reciprocal rank fusion and an identifier-aware reranker. Answers carry citations from the retrieved allowlist. Repository content is untrusted evidence.

Agent tools are typed and bounded. Source remains unchanged until explicit approval. Proposed patches are staged, displayed as unified diffs, validated against original file hashes and optionally tested in disposable, resource-limited Docker containers. Docker absence yields an unavailable result. Evaluation runs persist actual retrieval metrics for four strategies, with explicitly labeled keyword and citation proxies for answer assessment.

## Directory layout

```
backend/app/             configuration, persistence, API, providers, ingestion,
                         parsing, retrieval, dependencies, jobs, agents, sandbox, evaluations
backend/alembic/         database migrations
backend/tests/           behavioral, security and API integration tests
frontend/src/app/        landing, dashboard and repository workspace
frontend/src/components/ shared UI and feature components
frontend/src/lib/        typed API client
frontend/tests/          browser happy path
demo-repository/         small checkout/auth repository with a reproducible bug
docs/                   architecture, RAG, agent, security, evaluation, interview guide
scripts/                local startup and validation
```

## Phases and verification

1. Foundation: configuration, schema/migrations, health, Compose and interface contract. Validate health and migration.
2. Ingestion: GitHub and ZIP, parsing/chunks, jobs. Validate demo indexing, paths and limits.
3. RAG: providers, retrieval, fusion, reranking, grounded answers and citations. Validate ranking and source locations.
4. Intelligence: file browsing, imports and impact traversal. Validate known demo edges.
5. Agent: explicit validated tools, bounded loop and persisted traces. Validate errors and limits.
6. Debugging: isolated execution, staged patches, diffs, approval/rejection. Validate conflict protection and sandbox-unavailable behavior.
7. Evaluations: dataset and executed four-strategy comparison. Validate metric arithmetic and persistence.
8. Polish: responsive frontend, theme, failures, caching/logs/security; build, automated tests and browser happy path.
9. Documentation: reproducible setup, engineering decisions, limitations, interview guide and actual-feature resume bullets.

Each phase is recorded in docs/development-log.md with verification results. Independent frontend and agent/evaluation work proceeds in parallel against docs/api-contract.md.

## Dependencies and risks

Python: FastAPI, Pydantic settings, SQLAlchemy, Alembic, psycopg, pgvector, Redis/RQ, httpx, Tree-sitter language grammars, multipart, pytest. Frontend: Next.js, React, Tailwind, Lucide, syntax highlighting, Playwright. Docker: PostgreSQL/pgvector and Redis.

Docker daemon is currently unavailable on this machine. Use SQLite and local jobs to validate the real app here; report sandbox execution as unavailable. Docker Compose remains the production-style path. Offline embeddings are feature-hash vectors and offline responses are extractive evidence summaries, not neural semantic reasoning. API-key-configured providers upgrade these independently. Imports are conservative file edges, not whole-program static analysis. Main risks: untrusted content/ZIPs, clone resource usage, LLM grounding, patch conflicts, sandbox isolation and provider availability.

## MVP versus later work

MVP includes every demonstrable user flow: import, progress, ask/citations/retrieval inspection, files, dependencies/impact, agent traces and proposed diff approval, sandbox interface and genuine evaluations. Later enhancements: authenticated multi-tenant deployment, incremental/commit-aware indexing, trained local embeddings/cross-encoder, richer interprocedural analysis, distributed vector search, private GitHub OAuth and hardened remote sandbox infrastructure. Do not claim these as implemented.

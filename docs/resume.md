# Resume material

Use these bullets only for features you can demonstrate. Add numbers only after
recording the actual experiment, dataset, operating mode and environment.

- Built RepoPilot with Next.js, FastAPI and PostgreSQL/pgvector, combining
  code-aware Python/JavaScript/TypeScript indexing, BM25/vector retrieval,
  reciprocal rank fusion and reranking to return repository-grounded answers
  with source citations.
- Implemented a constrained debugging workflow with validated tools, persisted
  action traces, a Docker test-sandbox interface and staged Git diffs requiring
  human approval and source-content checks before application.
- Created a reproducible demo regression and an evaluation dashboard executing
  six source-grounded cases across four retrieval strategies, recording Recall@K,
  MRR, latency and explicit keyword/citation-validity proxies.

When discussing these bullets, disclose that no-key mode uses feature hashing
and extractive summaries, the local planner has limited repair scope, and Docker
execution can be unavailable. A sandbox interface/control test is not evidence
that hostile code containment was proven. The small demo dataset is not a broad
accuracy benchmark.

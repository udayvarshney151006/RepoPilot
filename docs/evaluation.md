# Evaluation methodology

The Evaluations page compares actual executed retrieval strategies against
source-grounded cases. It starts empty; a graph/table is populated only after a
run. Results are persisted with status, error and per-case observations so a
number can be traced back to a question and retrieved evidence.

## Dataset format

The bundled [demo dataset](../demo-repository/evaluation.json) contains six
questions whose files and symbols exist in the demo. An example is:

```json
{
  "question": "Where is JWT token signature and expiration validation implemented?",
  "expected_file": "shop/auth.py",
  "expected_symbol": "validate_token",
  "expected_answer_keywords": ["signature", "exp", "HS256"]
}
```

The expected file/symbol identifies an acceptable evidence unit, and keywords
provide a transparent answer-coverage proxy. Cases can be supplied for another
repository; demo expectations should not be copied into an unrelated repository.
Paths refer to indexed relative paths. Keep expected symbols aligned with the
parser's emitted names and inspect per-case output when a case misses.

The application excludes `evaluation.json` from code chunks so ground-truth
questions and answers cannot leak into the retrieval corpus. It remains visible
in the file browser as repository metadata.

## Strategies

Each run evaluates the same repository/questions/K using:

1. `vector`: cosine ranking from the configured embedding representation.
2. `bm25`: lexical identifier-aware ranking.
3. `hybrid`: reciprocal rank fusion of both candidate lists.
4. `hybrid_rerank`: hybrid candidates followed by the configured local reranker.

Offline vectors are feature hashes, and offline reranking is a heuristic. Results
from that mode must be labeled accordingly; they cannot establish the performance
of neural embeddings or a trained cross-encoder.

## Metrics and interpretation

| Metric | Calculation / meaning | Limitation |
| --- | --- | --- |
| Recall@K | Fraction of cases whose expected file/symbol appears in the first K results | Each case labels one acceptable evidence target; this is a hit-rate-style recall proxy, not recall over all relevant source |
| MRR | Mean reciprocal rank `1/r` of the first expected match, with 0 for a miss | Rewards a single early target; does not measure completeness of context |
| Average latency | Mean observed milliseconds for retrieval plus generation per case | Depends on provider, machine, corpus, warm caches and context size |
| Retrieved count | Mean actual returned chunks | A larger context is not automatically better evidence |
| Answer keyword coverage | Fraction of expected keywords found in generated/extracted text | Keywords can appear in a wrong answer; does not measure semantic correctness |
| Citation validity | Fraction of citations whose ID, path, symbol, lines and content match indexed evidence and the retrieved allowlist | A real citation can support an unrelated claim; not semantic faithfulness |
| Tokens | Provider-reported input/output usage when available | Missing usage is unavailable, not proof of zero provider consumption |
| Estimated cost | Reported usage multiplied by configured prices | Pricing must be configured; excludes infrastructure and other requests |

For example, relevant ranks `[1, 2, missing]` give MRR
`(1 + 1/2 + 0)/3 = 0.5`. With K=5, two of those three cases are retrieved, so
the recall proxy is `2/3`. These are explanatory arithmetic examples, not project
benchmark results.

Latency must be described according to the actual measured code boundary. UI
request duration also includes network/polling; evaluation timings are not a
guarantee of interactive production latency. Inspect stage-level metrics for
retrieval, reranking and generation when comparing systems.

## Run and inspect

1. Index the bundled demo and wait for ready.
2. Open Evaluations and run with the seeded cases.
3. Compare strategies, then inspect questions and retrieved paths/symbols.
4. Investigate a miss using Ask Repo's retrieval inspection and file explorer.
5. Change one retrieval/provider component, reindex if required, and repeat on
   the same cases before making a performance claim.

The API can run custom cases:

```text
POST /api/repositories/{repository_id}/evaluations
{"k": 5, "cases": [{"question": "...", "expected_file": "...",
 "expected_symbol": "...", "expected_answer_keywords": ["..."]}]}
```

If a repository has no usable supplied dataset, the app can generate limited
identifier-discovery cases from its actual indexed symbols. These are labeled
generated ground truth, not independent developer questions.

Poll `GET /api/evaluations/{id}` for persisted status/results. Failed provider or
job execution should display an error rather than a prefilled metric table.
Token/cost fields are optional when unavailable.

## What the demo establishes

The small dataset verifies plumbing, source identity, rank arithmetic and
strategy comparison on known source. It has exact identifiers and is authored
alongside the source, so it favors lexical matching and is not an unbiased
benchmark. No project-wide accuracy claim follows from it.

An actual six-case/four-strategy run is preserved in
[demo-evaluation-run.json](demo-evaluation-run.json), with provenance and its
local-mode limits in [validation.md](validation.md). It is an executed sample
artifact, not data used to prepopulate the dashboard.

For stronger evidence, create held-out questions from independent developers,
include paraphrases, multi-file flow questions and unanswerable queries, and use
multiple languages/repository sizes. Review answers against source with explicit
labels for correctness, evidence sufficiency and citation entailment. Record
embedding/model versions, index generation, K, dataset revision, warm/cold state
and run environment. Repeat timings rather than interpreting one small sample.

## Alternatives, tradeoffs and scale

Keyword proxies are cheap and explainable; manual labels are stronger but costly.
LLM-as-judge can assess nuanced answers, but needs calibration, independent
evidence and checks for judge bias. Pairwise judgments and blinded source review
can complement retrieval metrics. Larger eval suites should use versioned
datasets, queued batches, bounded provider concurrency, per-case failures and
cost budgets. Add regression gates only after defining a meaningful baseline and
tolerance; do not optimize the entire system for six demo questions.

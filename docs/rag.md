# Retrieval, generation and citations

RAG means retrieval-augmented generation: find relevant evidence first, then let
an answer generator use that evidence. RepoPilot indexes source units so each
piece of evidence carries a path, symbol and source range. Repository content is
data inside the prompt; it is not an instruction channel.

## Code-aware indexing

A syntax tree exposes functions, classes, methods and imports. Tree-sitter can
produce trees even in the presence of syntax errors and supports multiple
languages; see the [official introduction](https://tree-sitter.github.io/tree-sitter/).
RepoPilot uses language grammars for Python, JavaScript and TypeScript. It never
imports a repository module to discover its functions. Bounded fallback chunks
keep unsupported or unparseable text inspectable.

Chunk metadata includes repository, file, language, symbol name/type, start/end
lines, content and embedding. A function boundary preserves meaning better than
a random character window. Oversized symbols split into line-preserving pieces
with at most 100 lines and 6,000 UTF-8 bytes, retaining shared symbol metadata.
A single oversized line cannot be truncated while preserving full-line citations,
so ingestion skips that file and records an indexing notice. Overlapping
module/class chunks can introduce
duplicate evidence, which retrieval must limit.

Alternatives include Python `ast`, Babel for JavaScript, language servers or fixed
windows. Language-specific tools offer richer semantic resolution; Tree-sitter
keeps the MVP uniform. At scale, parse only changed files and reuse embeddings
for unchanged content rather than rebuilding every commit.

## Dense/vector retrieval

An embedding maps text into a numeric vector. A trained embedding model can make
related phrases close even when their literal words differ. Cosine similarity is
the angle-based comparison:

`cosine(a,b) = dot(a,b) / (norm(a) * norm(b))`.

Magnitude is normalized so direction drives the comparison. Zero vectors need
safe handling. Similarity is a retrieval signal, not a calibrated probability
that an answer is correct.

The offline provider uses fixed-size feature hashing over tokens and normalizes
the result, with a small explicit synonym mapping. Hash collisions and token overlap limit quality; it is **not a neural
semantic model**. A configured external embedding provider returns learned
vectors. Provider/model/dimension must remain consistent between chunks and
queries; changing provider/model requires reindexing. This MVP fixes the vector
dimension at 384; another dimension also needs a schema/configuration change.

PostgreSQL uses native pgvector storage/retrieval; SQLite uses JSON vectors and
local cosine scoring. A vector search boundary allows a dedicated store later.
SQLite search is exact over its local vectors. The PostgreSQL migration adds a
cosine HNSW index; HNSW/IVFFlat trade search speed against recall and require
measured tuning, including repository filters, at larger scale. Compare those
changes with the same evaluation questions rather than assuming they improve
quality.

## Lexical retrieval

BM25 scores terms using corpus rarity, document length and diminishing returns
for repeated terms. Rare identifiers such as `validate_token` should carry more
weight than words appearing everywhere. Code tokenization includes symbol and
path information so a query containing a function or filename can retrieve its
definition. Ingestion persists chunk term frequencies, document frequencies and
average lengths in a per-repository JSON artifact keyed to the index generation
and exact chunk IDs. Query-time loading verifies the artifact; missing, stale or
invalid data rebuilds from indexed source. A cache retains at most eight corpora
within a 64 MiB estimated weight budget, avoiding repeated corpus tokenization
while bounding retained state. The score computation still scans corpus entries
and is not an external inverted-postings engine.

Lexical search is strong at exact names, error strings and route fragments. It
is weaker when a user describes behavior with different vocabulary. Alternatives
are simple keyword counts, PostgreSQL full-text search or OpenSearch; a small
in-process BM25 scorer is easy to inspect, while an external index helps large
corpora and incremental updates.

## Hybrid fusion and reranking

The query performs lexical and vector candidate searches. Reciprocal rank fusion
combines ranks rather than adding incompatible raw BM25 and cosine scores:

`RRF(chunk) = sum_over_rankings(1 / (60 + rank(chunk)))`.

A chunk appearing high in both lists receives more support. Absent chunks
contribute nothing. Ranks are one-based. Deduplication uses chunk identity;
simply concatenating lists would not express agreement or handle duplicates.

The hybrid rerank strategy selects a larger candidate pool before reducing it
to the requested context size. The local reranker favors token coverage and
matches in symbols/paths along with fused rank. Its interface can be replaced by
a learned cross-encoder. A cross-encoder jointly reads query and candidate and
can model richer relationships, at the cost of inference latency. It is not
implemented by relabeling a keyword heuristic as an AI model.

There is no universal winning strategy. With offline hashed vectors and exact
identifier questions, BM25 may already perform well. The Evaluations page
compares vector, BM25, hybrid and hybrid with reranking on actual indexed code.

## Grounded generation

The generator receives the question and a bounded allowlist of retrieved chunks.
The selected source/path/symbol context has a 30,000-character budget; serialized
metadata and the question add overhead to the provider request. Context can have
fewer than K chunks when another chunk does not fit.
The instructions require evidence-only answers, clear uncertainty and references
to actual paths/symbols. External output must be constrained back to allowed
citations. Offline output extracts source facts from that evidence rather than
claiming to reason beyond it.

Citations contain chunk ID, path, symbol, line range, source content and score.
The browser opens indexed source, making a claim reviewable. A valid source
location does **not** establish that every nearby claim follows from the code.
Reindex after edits to keep ranges consistent; provider calls and caches must
use the repository's current index generation.

If evidence is weak, answer with uncertainty instead of inventing files. Hybrid
ranking still can return irrelevant positive-overlap chunks, and prompt rules
cannot guarantee factuality. Better calibration needs held-out unanswerable
questions, entailment checks and reviewer labels.

## Caching and observations

Optional Redis cache entries include repository index generation, provider,
question and retrieval strategy, with a short TTL. Reindexing changes the
generation, preventing reuse of pre-edit answers. Redis absence should degrade
to a real query, not a fabricated cached success.

Responses record retrieval, reranking, generation and total milliseconds, context
count, model and provider-reported tokens when available. Cost is unavailable
unless pricing is configured. Measure the entire request for user latency and
separate stages when identifying bottlenecks. Local timings are machine- and
dataset-specific.

## Interview tradeoffs

RAG bounds context and gives citations but can miss a necessary file. Smaller
chunks improve precision but lose flow; larger chunks preserve context but waste
tokens. Hybrid search reduces dependence on one retrieval signal but adds work.
Reranking refines a shortlist but cannot recover a relevant chunk never retrieved.
Caching improves repeated requests but requires invalidation. Provider
abstractions improve replaceability but do not make models behaviorally
interchangeable: reindexing and evaluation are part of a provider migration.

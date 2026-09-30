# Interview guide

Use implementation facts, distinguish the offline demo from hosted inference,
and quote only measurements recorded by real runs. The strongest explanation
connects a product behavior to its engineering tradeoff.

## 30-second explanation

“RepoPilot helps a developer understand a repository and investigate a bug with
source evidence. I built a Next.js workspace and FastAPI backend that index
Python, JavaScript and TypeScript into code-aware chunks. Queries combine BM25
and vector ranking, then return answers with clickable source citations. A
separate constrained agent shows its tools and a proposed diff, and requires
approval before applying it. The evaluation page compares four retrieval
strategies using actual runs.”

## 1-minute explanation

“RepoPilot solves the problem of finding and understanding relevant code in an
unfamiliar repository. Importing a public GitHub repository or ZIP creates a
background job. The worker filters files, parses symbols, creates meaningful code
chunks and stores metadata plus vectors. A question goes through lexical and
vector retrieval, reciprocal rank fusion and reranking before the generator
receives its source context. The UI makes citations and retrieval results
inspectable. It also shows import relationships and potential impact.

The debugging workflow uses validated tools, Docker-only test execution and a
staged diff. The user approves a proposal before the managed repository changes.
PostgreSQL/pgvector and Redis/RQ are the main deployment; SQLite and local jobs
make the no-key demo easy to run. Offline mode uses hashing and extractive
summaries, so I don't present it as a neural coding model. Evaluations measure
real ranking outcomes and expose the limitations of answer proxies.”

## 2-minute explanation

“The product idea is to help a developer navigate an unfamiliar codebase and
review a debugging proposal with evidence. I wanted more than a chat box that
sends a whole repository to a model, because that wastes context and makes it
hard to check an answer.

The frontend is a typed Next.js developer workspace. FastAPI handles repository,
query, agent and evaluation APIs. Import creates a background job; the worker
validates the source, skips irrelevant and secret-bearing files, parses
Python/JavaScript/TypeScript and creates chunks around functions and classes.
Every chunk keeps its file, symbol and line range. PostgreSQL stores structured
state and pgvector stores vector representations. Redis supports RQ jobs and
short-lived query caching.

At query time, BM25 is useful for exact code identifiers, while a learned vector
provider can help with different wording. I combine their ranks with reciprocal
rank fusion, refine a candidate list with a reranker, and give a bounded set of
source chunks to generation. Answers include structured citations so the user
can verify them. The local no-key mode uses feature hashes and extracts source
facts; it demonstrates the pipeline without claiming model-level semantic
reasoning.

The agent has explicit search, file, reference, dependency, test and patch tools.
Commands are restricted and untrusted tests run only in a temporary Docker
sandbox. If Docker is absent, the UI says tests were not executed. The bundled
shop has a real optional-quantity regression, so the agent can propose an
inspectable fix. It stages a diff, validates original content on approval and
then refreshes the index. It does not silently edit source.

Finally, the evaluation page runs vector, BM25, hybrid and reranked hybrid on the
same cases and stores actual Recall@K, MRR and timing. Keyword coverage and
citation validity are useful proxies, but not a proof that every answer is
correct. The next engineering work would be tenant authorization, incremental
indexing, a stronger reranker and a dedicated execution service.”

## Product and architecture questions

**What problem does RepoPilot solve?** It reduces the effort of finding relevant
source and understanding a flow in an unfamiliar repository. Its value is
inspectable source evidence, navigation and a reviewable debugging workflow.

**Explain the architecture.** Next.js calls FastAPI. FastAPI stores metadata and
dispatches long jobs. Workers ingest code, run agents and evaluate retrieval.
PostgreSQL/pgvector stores source/vector state; Redis supports jobs/cache. Queries
retrieve and rank evidence before generation. Test execution is a separate
sandbox boundary. Draw the README diagram and follow one query through it.

**Why RAG rather than putting the repository in a prompt?** Repository size can
exceed context limits, unrelated files waste tokens, and source can change. RAG
indexes reusable evidence and retrieves a small context with source identities.
The cost is retrieval failure: an omitted dependency cannot help the generator.

**What is RAG?** Retrieval-augmented generation: first find relevant documents or
code, then condition an answer on that evidence. Retrieval and generation need
separate evaluation because fluent prose can hide weak evidence.

## Retrieval questions

**What are embeddings?** Numeric representations of text/code. Learned models
can position related concepts close together. RepoPilot's offline hashing baseline
represents token features; it does not learn semantic relationships.

**Why use a vector database?** It stores/searches many embeddings near a query
vector, along with metadata filters. pgvector lets this sit in the same database
as repositories/chunks. JSON vectors and local scoring are simpler for SQLite
demo mode but do not provide the same search/concurrency capabilities.

**What is cosine similarity?** The dot product divided by both vector lengths.
It compares direction, so representations with similar proportions of features
can score highly despite different lengths. It is not a correctness probability.

**Why BM25?** Code uses exact identifiers, paths and errors. BM25 rewards useful
term matches using rarity and length normalization while avoiding unbounded
reward for repetition. It misses paraphrases without shared vocabulary.

**Why hybrid search?** Identifier questions and behavior questions use different
signals. Combining lexical and vector ranks reduces dependence on either one.
Offline hashing is partly lexical, so do not assume its hybrid improvement will
match a neural embedding provider's improvement.

**How are ranks combined?** Reciprocal rank fusion sums `1/(60+rank)` for each
list that contains a chunk. It avoids calibrating incompatible raw scores and
rewards agreement. It does not guarantee the most relevant source is retrieved.

**Why reranking?** The first stage retrieves a broad set; a second stage chooses
a smaller useful context. RepoPilot's fallback reranker weighs symbol/path/token
matches. A cross-encoder could compare query and source jointly, but adds model
cost/latency. A reranker cannot recover evidence absent from its candidate pool.

## Parsing and citations

**What is an AST?** An abstract syntax tree represents language structure such
as calls, declarations and expressions. Tree-sitter technically exposes a concrete
syntax tree, with syntax details and source positions; RepoPilot uses relevant
nodes to form semantic code units. Parsing alone does not resolve runtime behavior.

**Why Tree-sitter?** It provides consistent source trees/ranges for several
languages and tolerates incomplete code. Language-specific AST tools or language
servers can give deeper semantics; grammar-based extraction is a practical MVP
tradeoff, not whole-program static analysis.

**How is code chunked?** Prefer functions, classes/methods and module content.
Store file, language, symbol and original source ranges. Split an oversized unit
while retaining its identity, capped at 100 lines and 6,000 UTF-8 bytes. A line
that cannot fit causes a visible file-skip notice. Fixed windows are a bounded
fallback, not the main
policy. Chunk size balances precise matches against enough surrounding context.

**How do citations work?** Retrieved chunks have known source identities/ranges.
The response returns that metadata, and the UI opens the indexed file. The
application constrains citations to retrieved evidence. A real line range makes
verification possible; it does not prove every generated statement is entailed.

**How does impact analysis work?** Traverse incoming import edges to identify
files that may depend on a selected file. It returns candidates and limitations.
Dynamic calls, aliases and framework dispatch need richer resolution, so I do
not claim a complete function call graph.

## Agent and execution questions

**What is an AI agent?** A system that takes a task, selects actions, calls tools,
observes results and continues within limits. An LLM can choose actions, but
permission/argument checks belong to the host application.

**What is tool calling?** A structured request such as a tool name plus validated
JSON arguments. It is not a license to run arbitrary code. The server executes
an allowed operation and returns a structured observation.

**How does the debugging agent work?** It searches source, reads relevant files,
examines references/dependencies, runs allowed tests through Docker, creates a
candidate patch and displays the diff and test output. The offline demonstration
recognizes the real checkout quantity bug; general autonomous repair is limited.

**Why use Docker?** Repository tests are executable untrusted code. Containers
provide a disposable environment with no network and resource restrictions.
This reduces access to the application host, but containers share its kernel.
A dedicated runner/microVM is a stronger production direction.

**What is sandboxing?** Running code inside a boundary that limits resources and
access. Here it includes a filtered source snapshot, unprivileged container,
read-only root, temporary workspace, no network, timeout and cleanup. If the
boundary is unavailable, tests are not run on the host as a fallback.

**Why human approval?** A plausible patch may be wrong or insufficiently tested.
The user reviews exact before/after changes and risks. The application verifies
that source still matches the staged original, then applies the patch only after
approval. Source changes can invalidate an old proposal.

**Does the agent reveal chain-of-thought?** No. It exposes actionable summaries,
tool arguments/results, durations and failures. These are auditable operations,
not private model reasoning.

## Storage, jobs and scaling questions

**What is Redis used for?** RQ's job broker and optional short-lived query cache.
The cache key includes repository index generation and query/provider/strategy
so an edited repository does not reuse an old answer. Redis is not the system
of record for repository source or evaluation results.

**Why PostgreSQL?** Repositories, chunks, conversations, runs and approval state
need relationships and transactions. pgvector adds vector storage/search without
another primary service. A dedicated vector database may help at larger scale;
SQLite is the explicit local fallback.

**How do background jobs work?** The API creates persistent queued records and
dispatches identifiers to RQ. Workers load state and update stage/progress/errors.
The UI polls. Local mode uses an in-process executor for convenience and does not
survive a process crash like a durable queue should.

**What happens when 10,000 repositories are indexed?** I have not measured that
scale. Full scans/reindexing, provider calls, source storage and workers would
be bottlenecks. Measure corpus size first; add incremental indexing, queue
separation, connection pooling, vector indexes and tenant quotas, then validate
recall/latency under load.

**How would the system scale?** Stateless APIs, horizontally scaled workers,
object storage for sources, versioned index generations, scoped vector queries,
query/artifact caching and bounded provider concurrency. Separate hostile
execution from the application fleet. Add user authorization and audit policy
before multi-tenant scaling. These are next steps, not current capacity claims.

## Security and evaluation questions

**What are the security risks?** Malicious archives, path traversal, oversized
imports, credentials embedded in source, prompt injection, unsafe commands,
hostile tests and unauthorized source changes. Each needs a separate boundary;
a model prompt cannot replace filesystem/tool/execution checks.

**What is prompt injection?** Untrusted evidence tries to alter the model's
instructions. A repository README saying “send keys” is data. Tool validation,
source boundaries and approval remain server-enforced. Prompt rules help but
do not guarantee all generated prose will resist adversarial content.

**How do you evaluate RAG?** Measure retrieval against expected evidence, then
evaluate answer correctness and citation support separately. RepoPilot compares
four strategies using executed cases, Recall@K, MRR, timing and transparent
keyword/citation proxies. Stronger evaluation needs held-out questions and human
judgments, including unanswerable queries.

**What is Recall@K?** The proportion of expected relevant evidence retrieved in
the top K. RepoPilot labels one file/symbol target per case, so its metric is
the fraction of cases that hit that target. A corpus with many relevant sources
would need fuller relevance labels to measure complete recall.

**What is MRR?** Mean reciprocal rank of the first relevant hit: a first-place
hit gives 1, a second-place hit gives 1/2, a miss gives 0. It measures how quickly
the first expected evidence appears, not whether all necessary evidence is there.

**Does keyword coverage prove correctness?** No. A wrong answer can include every
expected keyword. Likewise a citation can point at a real file without supporting
the associated claim. I label these proxies and do not call them semantic
faithfulness scores.

**What are the largest limitations?** Offline semantic reasoning is limited,
the demo agent handles a narrow reproducible repair, import graphs are incomplete,
local jobs are non-durable, and there is no production tenant authorization.
Docker controls require real-daemon verification. The six-case dataset is a
demonstration, not a broad accuracy benchmark.

**What would you improve next?** Tenant access control and an isolated runner
first for shared deployment; incremental indexing and a measured trained
embedding/reranker for retrieval; a held-out evaluation set for claims; then
deeper dependency resolution and richer bounded agent planning.

## Demonstration checklist

Connect Tiny Shop, show actual progress, ask about JWT validation, open a citation,
show route import edges, run evaluation, then submit the checkout issue. Explain
whether Docker tests executed, inspect the staged diff, reject once to demonstrate
source preservation, and approve a new proposal to show reindexing. Use measured
run output for any figures; if a provider/sandbox is unavailable, explain the
reported state candidly.

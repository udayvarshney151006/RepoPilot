export interface Repository {
  id: string;
  name: string;
  source_url: string | null;
  status: string;
  error: string | null;
  file_count: number;
  chunk_count: number;
  languages: Record<string, number> | string[];
  created_at: string;
  indexed_at: string | null;
  embedding_provider: string;
  index_warnings?: string[];
}
export interface Job {
  id: string;
  status: string;
  stage: string;
  progress: number;
  error: string | null;
}
export interface FileEntry {
  path: string;
  language: string;
  line_count: number;
  size_bytes: number;
}
export interface CodeFile extends FileEntry {
  content: string;
  symbols: {
    name: string;
    type: string;
    start_line: number;
    end_line: number;
  }[];
}
export interface Citation {
  chunk_id: string;
  file_path: string;
  symbol_name: string | null;
  start_line: number;
  end_line: number;
  content: string;
  score: number;
}
export interface QueryResult {
  answer: string;
  citations: Citation[];
  retrieval: Citation[];
  conversation_id: string;
  mode: string;
  metrics: {
    retrieval_ms: number;
    reranking_ms: number;
    llm_ms: number;
    total_ms: number;
    retrieved_chunks: number;
    model: string;
    input_tokens: number | null;
    output_tokens: number | null;
    estimated_cost: number | null;
  };
}
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  messages: {
    role: string;
    content: string;
    citations: Citation[] | null;
    metrics: QueryResult["metrics"] | null;
  }[];
}
export interface Graph {
  nodes: { id: string; path: string; language: string }[];
  edges: { source: string; target: string; kind: string }[];
  limitations: string | string[];
}
export interface Impact {
  path: string;
  affected_files: string[];
  dependencies: string[];
  explanation: string;
}
export interface AgentRun {
  id: string;
  repository_id: string;
  task: string;
  status: string;
  summary: string | null;
  error: string | null;
  created_at: string;
  steps: {
    tool: string;
    arguments: Record<string, unknown>;
    result: unknown;
    duration_ms: number;
    success: boolean;
    summary: string;
  }[];
  patch: {
    diff: string;
    files: {
      path: string;
      before: string;
      after: string;
      original_hash: string;
    }[];
    explanation: string;
    risks: string | string[];
  } | null;
  test_results: Record<string, unknown>[];
}
export interface EvaluationCase {
  question: string;
  expected_file: string;
  expected_symbol: string | null;
  expected_answer_keywords: string[];
}
export interface Dataset {
  id: string;
  name: string;
  cases: EvaluationCase[];
}
export interface EvaluationMetric {
  strategy: string;
  recall_at_k: number;
  mrr: number;
  avg_latency_ms: number;
  avg_retrieved_chunks: number;
  answer_keyword_coverage: number;
  citation_validity: number;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: number | null;
}
export interface EvaluationRun {
  id: string;
  status: string;
  error: string | null;
  created_at: string;
  metrics: EvaluationMetric[];
  results: Record<string, unknown>[];
}
export type Settings = Record<string, unknown>;

import type {
  AgentRun,
  CodeFile,
  Conversation,
  Dataset,
  EvaluationRun,
  FileEntry,
  Graph,
  Impact,
  Job,
  QueryResult,
  Repository,
  Settings,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((x: { msg: string }) => x.msg).join("; ")
          : "The API could not complete this request. Check that the backend is running.",
      response.status,
    );
  }
  return data as T;
}
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
export const api = {
  repositories: () => request<Repository[]>("/repositories"),
  repository: (id: string) => request<Repository>(`/repositories/${id}`),
  status: (id: string) =>
    request<{ repository: Repository; job: Job | null }>(
      `/repositories/${id}/status`,
    ),
  import: (url: string) => post<Repository>("/repositories", { url }),
  demo: () => post<Repository>("/repositories/demo"),
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<Repository>("/repositories/upload", {
      method: "POST",
      body,
    });
  },
  index: (id: string) => post<Job>(`/repositories/${id}/index`),
  files: (id: string) => request<FileEntry[]>(`/repositories/${id}/files`),
  file: (id: string, path: string) =>
    request<CodeFile>(
      `/repositories/${id}/files/${path.split("/").map(encodeURIComponent).join("/")}`,
    ),
  query: (
    id: string,
    question: string,
    strategy: string,
    conversation_id?: string,
  ) =>
    post<QueryResult>(`/repositories/${id}/query`, {
      question,
      strategy,
      conversation_id,
    }),
  conversations: (id: string) =>
    request<Conversation[]>(`/repositories/${id}/conversations`),
  graph: (id: string) => request<Graph>(`/repositories/${id}/dependencies`),
  impact: (id: string, path: string) =>
    request<Impact>(
      `/repositories/${id}/impact?path=${encodeURIComponent(path)}`,
    ),
  agents: (id: string) => request<AgentRun[]>(`/repositories/${id}/agent-runs`),
  agent: (id: string) => request<AgentRun>(`/agent-runs/${id}`),
  startAgent: (id: string, task: string) =>
    post<AgentRun>(`/repositories/${id}/agent-runs`, { task }),
  approve: (id: string) => post<AgentRun>(`/agent-runs/${id}/approve`),
  reject: (id: string) => post<AgentRun>(`/agent-runs/${id}/reject`),
  dataset: (id: string) =>
    request<Dataset>(`/repositories/${id}/evaluation-dataset`),
  evaluations: (id: string) =>
    request<EvaluationRun[]>(`/repositories/${id}/evaluations`),
  evaluation: (id: string) => request<EvaluationRun>(`/evaluations/${id}`),
  startEvaluation: (id: string, cases?: Dataset["cases"]) =>
    post<EvaluationRun>(`/repositories/${id}/evaluations`, {
      k: 5,
      ...(cases ? { cases } : {}),
    }),
  settings: () => request<Settings>("/settings"),
  health: () => request<Settings>("/health"),
};

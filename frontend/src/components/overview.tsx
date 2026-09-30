"use client";
import { useState } from "react";
import {
  Bot,
  Code2,
  Files,
  GitBranch,
  Layers3,
  MessageSquare,
  RefreshCw,
  Activity,
  ArrowUpRight,
  Clock,
  Check,
  Loader2,
} from "lucide-react";
import { useRepository } from "./workspace";
import { api } from "@/lib/api";
import { formatDate, useResource } from "@/lib/hooks";
import { Badge, ErrorState, PageHeading, PanelLink } from "./ui";
const stages = [
  "queued",
  "cloning",
  "parsing",
  "embedding",
  "indexing",
  "ready",
];
export function Overview({ id }: { id: string }) {
  const { repository: r, reload } = useRepository();
  const status = useResource(
    () => api.status(id),
    [id],
    r?.status === "ready" || r?.status === "failed" ? 0 : 1200,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!r) return null;
  const current = stages.indexOf(r.status);
  const job = status.data?.job;
  const languages = Array.isArray(r.languages)
    ? r.languages.map((x) => [x, 1] as const)
    : Object.entries(r.languages || {});
  const total = languages.reduce((s, [, n]) => s + Number(n), 0);
  return (
    <main className="page">
      <PageHeading
        eyebrow="REPOSITORY OVERVIEW"
        title={r.name}
        description="Your codebase, connected and in context."
        action={
          <button
            className="button secondary"
            disabled={busy || !["ready", "failed"].includes(r.status)}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                await api.index(id);
                await reload();
                await status.reload();
              } catch (e) {
                setError(e instanceof Error ? e.message : "Reindex failed.");
              } finally {
                setBusy(false);
              }
            }}
          >
            <RefreshCw size={15} className={busy ? "spin" : ""} /> Reindex
          </button>
        }
      />
      {(error || r.error) && <ErrorState error={error || r.error!} />}
      {r.index_warnings?.length ? (
        <details className="index-warnings">
          <summary>
            {r.index_warnings.length} indexing notices — some source was skipped
          </summary>
          <ul>
            {r.index_warnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </details>
      ) : null}
      <div className="overview-stats">
        <div className="card stat-card">
          <Files size={18} />
          <span>Source files</span>
          <strong>{r.file_count.toLocaleString()}</strong>
          <small>Filtered & parsed source</small>
        </div>
        <div className="card stat-card">
          <Layers3 size={18} />
          <span>Code chunks</span>
          <strong>{r.chunk_count.toLocaleString()}</strong>
          <small>Searchable code evidence</small>
        </div>
        <div className="card stat-card">
          <Code2 size={18} />
          <span>Languages</span>
          <strong>{languages.length}</strong>
          <small>
            {languages
              .slice(0, 3)
              .map(([x]) => x)
              .join(" · ") || "Awaiting parse"}
          </small>
        </div>
        <div className="card stat-card">
          <Clock size={18} />
          <span>Last indexed</span>
          <strong className="date-value">
            {r.indexed_at ? formatDate(r.indexed_at) : "Pending"}
          </strong>
          <small>
            {r.indexed_at
              ? new Date(r.indexed_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "Indexing in background"}
          </small>
        </div>
      </div>
      <section className="card indexing-panel">
        <div className="panel-title">
          <div>
            <h3>Repository indexing</h3>
            <p>
              {r.status === "ready"
                ? "Your repository is ready to explore."
                : r.status === "failed"
                  ? "Indexing stopped. Inspect the error and try reindexing."
                  : "Building code context in the background."}
            </p>
          </div>
          <Badge status={r.status} />
        </div>
        <div className="indexing-stages">
          {stages.map((stage, i) => (
            <div
              className={`indexing-stage ${i <= current ? "done" : ""} ${i === current ? "current" : ""}`}
              key={stage}
            >
              <span className="stage-circle">
                {i < current || r.status === "ready" ? (
                  <Check size={13} />
                ) : i === current ? (
                  <Loader2 className="spin" size={13} />
                ) : (
                  i + 1
                )}
              </span>
              <span>{stage}</span>
            </div>
          ))}
        </div>
        {job && r.status !== "ready" && (
          <div className="job-progress">
            <div>
              <span>{job.stage}</span>
              <span>
                {Math.round(
                  job.progress <= 1 ? job.progress * 100 : job.progress,
                )}
                %
              </span>
            </div>
            <progress
              max="100"
              value={job.progress <= 1 ? job.progress * 100 : job.progress}
            />
          </div>
        )}
      </section>
      <div className="overview-columns">
        <section className="card language-panel">
          <div className="panel-title">
            <h3>Language composition</h3>
            <Code2 size={17} />
          </div>
          <div className="language-bar">
            {languages.map(([name, n], i) => (
              <div
                key={name}
                style={{
                  width: `${(Number(n) / total) * 100}%`,
                  background: `var(--lang-${i % 5})`,
                }}
              />
            ))}
          </div>
          <div className="language-list">
            {languages.map(([name, n], i) => (
              <div key={name}>
                <span>
                  <i style={{ background: `var(--lang-${i % 5})` }} />
                  {name}
                </span>
                <span>
                  {Array.isArray(r.languages) ? "Detected" : `${n} files`}
                </span>
              </div>
            ))}
          </div>
          {!languages.length && (
            <p className="muted">Languages appear after parsing.</p>
          )}
        </section>
        <section className="card source-panel">
          <div className="panel-title">
            <h3>Source details</h3>
            <GitBranch size={17} />
          </div>
          <dl>
            <div>
              <dt>Origin</dt>
              <dd>
                {r.source_url?.startsWith("https://github.com/") ? (
                  <a href={r.source_url} target="_blank" rel="noreferrer">
                    {r.source_url.replace("https://github.com/", "")}{" "}
                    <ArrowUpRight size={12} />
                  </a>
                ) : (
                  "Local repository"
                )}
              </dd>
            </div>
            <div>
              <dt>Embedding provider</dt>
              <dd>{r.embedding_provider || "Pending"}</dd>
            </div>
            <div>
              <dt>Connected</dt>
              <dd>{new Date(r.created_at).toLocaleString()}</dd>
            </div>
          </dl>
        </section>
      </div>
      <div className="section-label mt-8 mb-4">CONTINUE EXPLORING</div>
      <div className="overview-actions">
        <PanelLink
          href={`/repositories/${id}/ask`}
          icon={<MessageSquare size={21} />}
          title="Ask your repository"
        >
          Follow a code flow with answers and clickable source citations.
        </PanelLink>
        <PanelLink
          href={`/repositories/${id}/agent`}
          icon={<Bot size={21} />}
          title="Investigate an issue"
        >
          Inspect tool actions, test output, and a proposed patch.
        </PanelLink>
        <PanelLink
          href={`/repositories/${id}/evaluations`}
          icon={<Activity size={21} />}
          title="Measure retrieval"
        >
          Compare four strategies using real evaluation results.
        </PanelLink>
      </div>
    </main>
  );
}

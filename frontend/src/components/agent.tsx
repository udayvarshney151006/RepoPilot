"use client";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Code2,
  GitPullRequest,
  Play,
  ShieldCheck,
  Terminal,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate, formatMs, useResource } from "@/lib/hooks";
import type { AgentRun } from "@/lib/types";
import { useRepository } from "./workspace";
import { DiffViewer } from "./code-viewer";
import {
  Badge,
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  PageHeading,
} from "./ui";

export function Agent({ id }: { id: string }) {
  const { repository, reload } = useRepository();
  const runs = useResource(() => api.agents(id), [id], 3000);
  const [selected, setSelected] = useState<string | null>(null);
  const [task, setTask] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [confirm, setConfirm] = useState(false);
  const run = useResource(
    () => (selected ? api.agent(selected) : Promise.resolve(null)),
    [selected],
    selected ? 1500 : 0,
  );
  useEffect(() => {
    if (!selected && runs.data?.length) setSelected(runs.data[0].id);
  }, [runs.data, selected]);
  async function start() {
    if (!task.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.startAgent(id, task);
      setSelected(next.id);
      setTask("");
      await runs.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start agent.");
    } finally {
      setBusy(false);
    }
  }
  async function decide(approve: boolean) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const result = approve
        ? await api.approve(selected)
        : await api.reject(selected);
      run.setData(result);
      setConfirm(false);
      await runs.reload();
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Patch decision failed.");
    } finally {
      setBusy(false);
    }
  }
  const current = run.data;
  return (
    <main className="page agent-page">
      <PageHeading
        title="Agent"
        description="Investigate with explicit tools. Review the evidence. Approve the change."
      />
      <div className="agent-security">
        <ShieldCheck size={16} />
        <span>Source changes require your approval.</span>
        <span>Commands execute only in an available restricted sandbox.</span>
      </div>
      {error && <ErrorState error={error} />}
      <form
        className="card task-composer"
        onSubmit={(e) => {
          e.preventDefault();
          void start();
        }}
      >
        <div className="task-composer-heading">
          <Bot size={18} />
          <label htmlFor="agent-task">What should the agent investigate?</label>
          <span>BOUNDED TOOL EXECUTION</span>
        </div>
        <textarea
          id="agent-task"
          rows={3}
          placeholder="Example: POST /checkout returns 500 when an item omits quantity. Investigate and propose a fix."
          value={task}
          onChange={(e) => setTask(e.target.value)}
          disabled={busy}
        />
        <div>
          <p>
            Specific symptoms and relevant file names help focus the
            investigation.
          </p>
          <button
            className="button primary"
            disabled={busy || !task.trim() || repository?.status !== "ready"}
          >
            {busy ? "Starting…" : "Start investigation"}
            <ArrowRight size={15} />
          </button>
        </div>
      </form>
      <div className="agent-layout">
        <aside className="run-list">
          <div className="section-label">
            INVESTIGATIONS <span>{runs.data?.length ?? 0}</span>
          </div>
          {runs.loading ? (
            <Loading label="Loading runs" />
          ) : runs.error ? (
            <ErrorState error={runs.error} retry={runs.reload} />
          ) : runs.data?.length ? (
            runs.data.map((r) => (
              <button
                className={`run-item ${selected === r.id ? "active" : ""}`}
                key={r.id}
                onClick={() => {
                  setSelected(r.id);
                  setExpanded(new Set());
                }}
              >
                <div>
                  <Bot size={14} />
                  <Badge status={r.status} />
                </div>
                <strong>{r.task}</strong>
                <span>
                  {formatDate(r.created_at)} · {r.id.slice(0, 8)}
                </span>
              </button>
            ))
          ) : (
            <div className="muted run-list-empty">
              Your investigations will appear here.
            </div>
          )}
        </aside>
        <section className="run-detail">
          {current ? (
            <>
              <div className="run-detail-title">
                <div className="flex items-center gap-3">
                  <Bot size={19} />
                  <h3>Investigation</h3>
                </div>
                <Badge status={current.status} />
              </div>
              <p className="run-task">{current.task}</p>
              {current.error && <ErrorState error={current.error} />}{" "}
              {current.summary && (
                <div className="run-summary">
                  <span className="tiny-label">OUTCOME</span>
                  <p>{current.summary}</p>
                </div>
              )}
              {["queued", "running"].includes(current.status) && (
                <div className="thinking">
                  <span className="pulse-dot" />{" "}
                  {current.status === "queued"
                    ? "Waiting for the job worker…"
                    : "Investigation in progress…"}
                </div>
              )}
              <div className="trace-heading">
                <h4>Actions taken</h4>
                <span>{current.steps.length} tool calls</span>
              </div>
              {!current.steps.length ? (
                <div className="muted py-4">
                  Tool actions appear here as the agent executes.
                </div>
              ) : (
                <div className="agent-trace">
                  {current.steps.map((s, i) => (
                    <div
                      className={`trace-step ${s.success ? "success" : "failure"}`}
                      key={i}
                    >
                      <button
                        className="trace-step-header"
                        onClick={() =>
                          setExpanded((old) => {
                            const next = new Set(old);
                            if (next.has(i)) next.delete(i);
                            else next.add(i);
                            return next;
                          })
                        }
                      >
                        <span className="trace-step-marker">
                          {s.success ? <Check size={13} /> : <X size={13} />}
                        </span>
                        <div>
                          <strong>
                            {s.summary || s.tool.replaceAll("_", " ")}
                          </strong>
                          <span>{s.tool}</span>
                        </div>
                        <span className="trace-duration">
                          <Clock size={11} />
                          {formatMs(s.duration_ms)}
                        </span>
                        {expanded.has(i) ? (
                          <ChevronDown size={15} />
                        ) : (
                          <ChevronRight size={15} />
                        )}
                      </button>
                      {expanded.has(i) && (
                        <div className="trace-output">
                          <div className="tiny-label">ARGUMENTS</div>
                          <pre>{JSON.stringify(s.arguments, null, 2)}</pre>
                          <div className="tiny-label">RESULT</div>
                          <pre>
                            {typeof s.result === "string"
                              ? s.result
                              : JSON.stringify(s.result, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {current.test_results.length > 0 && (
                <div className="test-results">
                  <h4>
                    <Terminal size={15} /> Sandbox execution results
                  </h4>
                  {current.test_results.map((result, i) => (
                    <div className="test-result" key={i}>
                      <div>
                        <Badge
                          status={String(
                            result.status ||
                              (result.available === false
                                ? "unavailable"
                                : result.success
                                  ? "completed"
                                  : "failed"),
                          )}
                        />
                        <span>
                          {String(result.command || "Test execution")}
                        </span>
                      </div>
                      <pre>
                        {String(
                          result.output ||
                            result.stdout ||
                            result.error ||
                            result.reason ||
                            JSON.stringify(result, null, 2),
                        )}
                      </pre>
                      {Boolean(result.stderr) && (
                        <pre>{String(result.stderr)}</pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {current.patch && (
                <Patch
                  run={current}
                  busy={busy}
                  onApprove={() => setConfirm(true)}
                  onReject={() => void decide(false)}
                />
              )}
            </>
          ) : selected && run.loading ? (
            <Loading label="Loading investigation" />
          ) : run.error ? (
            <ErrorState error={run.error} retry={run.reload} />
          ) : (
            <EmptyState
              icon={<Bot size={28} />}
              title="Make the investigation visible"
            >
              Start an agent task to inspect tool actions, sandbox results, and
              proposed source changes.
            </EmptyState>
          )}
        </section>
      </div>
      {confirm && current?.patch && (
        <Modal
          title="Apply this proposed patch?"
          onClose={() => setConfirm(false)}
        >
          <div className="modal-content">
            <p>
              The reviewed patch will be applied to the managed repository copy.
              Source hashes are checked for conflicting changes, and the
              repository will be reindexed.
            </p>
            <ul className="approval-files">
              {current.patch.files.map((f) => (
                <li key={f.path}>
                  <Code2 size={14} />
                  {f.path}
                </li>
              ))}
            </ul>
            <p className="muted">
              Sandbox results and risks remain available in the investigation.
            </p>
            <div className="modal-actions">
              <button
                className="button secondary"
                onClick={() => setConfirm(false)}
              >
                Cancel
              </button>
              <button
                className="button primary"
                disabled={busy}
                onClick={() => void decide(true)}
              >
                <Check size={15} />
                {busy ? "Applying…" : "Approve and apply"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </main>
  );
}
function Patch({
  run,
  busy,
  onApprove,
  onReject,
}: {
  run: AgentRun;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  const patch = run.patch!;
  const lines = patch.diff.split("\n");
  const additions = lines.filter(
      (l) => l.startsWith("+") && !l.startsWith("+++"),
    ).length,
    deletions = lines.filter(
      (l) => l.startsWith("-") && !l.startsWith("---"),
    ).length;
  return (
    <section className="patch-panel">
      <header>
        <div>
          <GitPullRequest size={17} />
          <h4>Proposed patch</h4>
        </div>
        <span>
          {patch.files.length} files <b className="text-green">+{additions}</b>{" "}
          <b className="text-red">−{deletions}</b>
        </span>
      </header>
      <p>{patch.explanation}</p>
      <div className="patch-files">
        {patch.files.map((f) => (
          <span key={f.path}>
            <Code2 size={12} />
            {f.path}
          </span>
        ))}
      </div>
      <DiffViewer diff={patch.diff} />
      <div className="patch-risk">
        <ShieldCheck size={14} />
        <div>
          <strong>Review considerations</strong>
          <p>
            {Array.isArray(patch.risks)
              ? patch.risks.join(" ")
              : patch.risks ||
                "Review the diff and available execution results before approval."}
          </p>
        </div>
      </div>
      {run.status === "awaiting_approval" ? (
        <div className="patch-actions">
          <span>
            <Clock size={13} /> Waiting for your decision
          </span>
          <div>
            <button
              className="button secondary"
              disabled={busy}
              onClick={onReject}
            >
              <X size={14} /> Reject
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={onApprove}
            >
              <Check size={14} /> Approve patch
            </button>
          </div>
        </div>
      ) : (
        <div className="patch-actions">
          <Badge status={run.status} />
        </div>
      )}
    </section>
  );
}

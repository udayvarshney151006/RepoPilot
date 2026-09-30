"use client";
import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Download,
  FlaskConical,
  Play,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  formatDate,
  formatMs,
  percent,
  strategyName,
  useResource,
} from "@/lib/hooks";
import type { EvaluationCase } from "@/lib/types";
import { useRepository } from "./workspace";
import {
  Badge,
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  PageHeading,
} from "./ui";

export function Evaluations({ id }: { id: string }) {
  const { repository } = useRepository();
  const dataset = useResource(() => api.dataset(id), [id]);
  const runs = useResource(() => api.evaluations(id), [id], 3000);
  const [selected, setSelected] = useState<string | null>(null);
  const run = useResource(
    () => (selected ? api.evaluation(selected) : Promise.resolve(null)),
    [selected],
    selected ? 1800 : 0,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datasetOpen, setDatasetOpen] = useState(false);
  const [custom, setCustom] = useState("");
  const [details, setDetails] = useState(false);
  useEffect(() => {
    if (!selected && runs.data?.length) setSelected(runs.data[0].id);
  }, [runs.data, selected]);
  async function start(cases?: EvaluationCase[]) {
    setBusy(true);
    setError(null);
    try {
      const r = await api.startEvaluation(id, cases);
      setSelected(r.id);
      setDatasetOpen(false);
      await runs.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Evaluation failed.");
    } finally {
      setBusy(false);
    }
  }
  function startCustom() {
    try {
      const parsed: unknown = JSON.parse(custom);
      if (!Array.isArray(parsed) || !parsed.length)
        throw new Error("Provide a nonempty JSON array of cases.");
      if (
        parsed.some(
          (c) =>
            typeof c.question !== "string" ||
            typeof c.expected_file !== "string" ||
            !Array.isArray(c.expected_answer_keywords),
        )
      )
        throw new Error(
          "Every case needs question, expected_file, and expected_answer_keywords.",
        );
      void start(parsed as EvaluationCase[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Invalid dataset JSON.");
    }
  }
  const current = run.data;
  const metrics = current?.status === "completed" ? current.metrics : [];
  return (
    <main className="page evaluations-page">
      <PageHeading
        title="Evaluations"
        description="Measure retrieval quality against known repository evidence."
        action={
          <button
            className="button primary"
            disabled={busy || repository?.status !== "ready"}
            onClick={() => void start()}
          >
            <Play size={14} />
            {busy ? "Starting…" : "Run evaluation"}
          </button>
        }
      />
      <div className="evaluation-intro card">
        <span className="evaluation-icon">
          <FlaskConical size={21} />
        </span>
        <div>
          <h3>Four strategies. One dataset.</h3>
          <p>
            Compare vector, BM25, hybrid, and reranked retrieval on the same
            questions. Every number below comes from an executed run.
          </p>
        </div>
        <button
          className="button secondary small"
          onClick={() => {
            setCustom(JSON.stringify(dataset.data?.cases || [], null, 2));
            setDatasetOpen(true);
          }}
        >
          <ClipboardList size={14} /> View dataset{" "}
          <span className="count-bubble">
            {dataset.data?.cases.length ?? "—"}
          </span>
        </button>
      </div>
      {error && <ErrorState error={error} />}{" "}
      {runs.error && <ErrorState error={runs.error} retry={runs.reload} />}
      <div className="evaluation-toolbar">
        <div className="section-label">
          <BarChart3 size={15} /> RETRIEVAL BENCHMARK
        </div>
        <select
          className="run-select"
          aria-label="Evaluation run"
          value={selected || ""}
          onChange={(e) => setSelected(e.target.value)}
        >
          <option value="" disabled>
            Select a run
          </option>
          {runs.data?.map((r) => (
            <option value={r.id} key={r.id}>
              {formatDate(r.created_at)} · {r.id.slice(0, 8)} · {r.status}
            </option>
          ))}
        </select>
        {current && <Badge status={current.status} />}
      </div>
      {current?.error && <ErrorState error={current.error} />}{" "}
      {selected && run.loading ? (
        <Loading label="Loading evaluation results" />
      ) : run.error ? (
        <ErrorState error={run.error} retry={run.reload} />
      ) : metrics?.length ? (
        <>
          <div className="evaluation-charts">
            <section className="card benchmark-chart">
              <div className="panel-title">
                <h3>Recall@5</h3>
                <span>Higher is better</span>
              </div>
              <div className="bar-chart">
                {metrics.map((m, i) => (
                  <div className="chart-row" key={m.strategy}>
                    <span>{strategyName(m.strategy)}</span>
                    <div>
                      <div
                        className="chart-bar"
                        style={{
                          width: `${Math.min(100, Math.max(0, m.recall_at_k * 100))}%`,
                          background: `var(--lang-${i % 5})`,
                        }}
                      />
                    </div>
                    <strong>{percent(m.recall_at_k)}</strong>
                  </div>
                ))}
              </div>
              <p className="chart-footnote">
                Fraction of questions retrieving the expected file or symbol in
                the top five.
              </p>
            </section>
            <section className="card benchmark-chart">
              <div className="panel-title">
                <h3>Average latency</h3>
                <span>Lower is better</span>
              </div>
              <div className="bar-chart">
                {metrics.map((m, i) => (
                  <div className="chart-row" key={m.strategy}>
                    <span>{strategyName(m.strategy)}</span>
                    <div>
                      <div
                        className="chart-bar"
                        style={{
                          width: `${(m.avg_latency_ms / Math.max(...metrics.map((x) => x.avg_latency_ms), 1)) * 100}%`,
                          background: `var(--lang-${i % 5})`,
                        }}
                      />
                    </div>
                    <strong>{formatMs(m.avg_latency_ms)}</strong>
                  </div>
                ))}
              </div>
              <p className="chart-footnote">
                Measured retrieval and generation time averaged over this run’s
                evaluation questions.
              </p>
            </section>
          </div>
          <section className="card evaluation-table-panel">
            <div className="panel-title">
              <h3>Strategy comparison</h3>
              <span className="measured-label">
                <span className="status-dot green-dot" /> Measured results
              </span>
            </div>
            <div className="table-scroll">
              <table className="metric-table">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Recall@5</th>
                    <th>MRR</th>
                    <th>Latency</th>
                    <th>Chunks</th>
                    <th>Keyword coverage</th>
                    <th>Citation validity</th>
                    <th>Tokens in / out</th>
                    <th>Est. cost</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.map((m, i) => (
                    <tr key={m.strategy}>
                      <td>
                        <span
                          className="strategy-dot"
                          style={{ background: `var(--lang-${i % 5})` }}
                        />
                        {strategyName(m.strategy)}
                      </td>
                      <td>{percent(m.recall_at_k)}</td>
                      <td>{m.mrr.toFixed(3)}</td>
                      <td>{formatMs(m.avg_latency_ms)}</td>
                      <td>{m.avg_retrieved_chunks.toFixed(1)}</td>
                      <td>{percent(m.answer_keyword_coverage)}</td>
                      <td>{percent(m.citation_validity)}</td>
                      <td>
                        {m.input_tokens ?? "—"} / {m.output_tokens ?? "—"}
                      </td>
                      <td>
                        {m.estimated_cost == null
                          ? "—"
                          : `$${m.estimated_cost.toFixed(6)}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="metric-note">
              Keyword coverage and citation validity are lightweight answer
              proxies. They do not establish semantic correctness or
              faithfulness. Unavailable provider usage is shown as —.
            </div>
          </section>
          <section className="card evaluation-details">
            <button
              className="details-toggle"
              onClick={() => setDetails(!details)}
            >
              <div>
                <ClipboardList size={16} />
                <h3>Per-question results</h3>
                <span>{current?.results.length} records</span>
              </div>
              {details ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
            {details && (
              <div className="evaluation-records">
                {current?.results.map((result, i) => (
                  <div className="evaluation-record" key={i}>
                    <div className="tiny-label">RECORD {i + 1}</div>
                    <pre>{JSON.stringify(result, null, 2)}</pre>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      ) : current && ["queued", "running"].includes(current.status) ? (
        <div className="card">
          <Loading label="Running real retrieval evaluations…" />
          <p className="muted text-center pb-6">
            Results appear after all four strategies finish.
          </p>
        </div>
      ) : (
        <div className="card">
          <EmptyState
            icon={<Activity size={28} />}
            title="A benchmark starts with a run"
            action={
              <button
                className="button primary"
                disabled={busy || repository?.status !== "ready"}
                onClick={() => void start()}
              >
                <Play size={14} /> Run first evaluation
              </button>
            }
          >
            Execute the dataset to compare retrieval strategies. Metrics will
            appear once the run completes.
          </EmptyState>
        </div>
      )}
      {datasetOpen && (
        <Modal
          wide
          title="Evaluation dataset"
          onClose={() => setDatasetOpen(false)}
        >
          <div className="modal-content">
            <p className="muted mb-5">
              {dataset.data?.name || "Repository evaluation dataset"}. Review
              seeded cases or edit the JSON to run a custom dataset.
            </p>
            {dataset.error && <ErrorState error={dataset.error} />}
            <label className="field-label" htmlFor="dataset-json">
              Question cases
            </label>
            <textarea
              id="dataset-json"
              className="dataset-editor mono"
              rows={17}
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
            />
            <p className="field-help">
              Each case contains question, expected_file, expected_symbol, and
              expected_answer_keywords.
            </p>
            {error && <ErrorState error={error} />}
            <div className="modal-actions">
              <button
                className="button secondary"
                onClick={() => setDatasetOpen(false)}
              >
                Close
              </button>
              <button
                className="button primary"
                disabled={busy || repository?.status !== "ready"}
                onClick={startCustom}
              >
                <Play size={14} /> Run this dataset
              </button>
            </div>
          </div>
        </Modal>
      )}
    </main>
  );
}

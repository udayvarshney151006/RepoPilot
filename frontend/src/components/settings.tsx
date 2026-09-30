"use client";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  Database,
  Layers3,
  Server,
  Settings2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { ErrorState, Loading, Logo, PageHeading, ThemeToggle } from "./ui";
const labels: Record<string, string> = {
  llm_provider: "Generation provider",
  llm_model: "Generation model",
  embedding_provider: "Embedding provider",
  embedding_model: "Embedding model",
  reranker_provider: "Reranker",
  database: "Database",
  jobs: "Job processing",
  sandbox: "Docker sandbox",
  mode: "Runtime mode",
  max_upload_bytes: "Maximum upload bytes",
  max_file_bytes: "Maximum file bytes",
  max_files: "Maximum source files",
  agent_max_steps: "Agent step limit",
  sandbox_enabled: "Sandbox enabled",
  sandbox_available: "Sandbox available",
  database_mode: "Database mode",
  job_mode: "Job mode",
};
function Value({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <span className="muted">Unavailable</span>;
  if (typeof value === "boolean")
    return (
      <span className={value ? "text-green" : "muted"}>
        {value ? "Enabled / available" : "Disabled / unavailable"}
      </span>
    );
  if (typeof value === "object")
    return <pre className="setting-json">{JSON.stringify(value, null, 2)}</pre>;
  return <span className="setting-value">{String(value)}</span>;
}
export function SettingsPanel({
  standalone = false,
}: {
  standalone?: boolean;
}) {
  const config = useResource(api.settings, []);
  const health = useResource(api.health, [], 10000);
  const body = (
    <main className="page settings-page">
      <PageHeading
        title="Settings"
        description="Inspect the providers and runtime powering this workspace."
        action={<ThemeToggle />}
      />
      <div className="settings-notice">
        <ShieldCheck size={17} />
        <p>
          Provider configuration is managed on the backend through environment
          variables. Only public configuration is displayed here.
        </p>
      </div>
      <div className="settings-grid">
        <section className="card settings-card">
          <div className="panel-title">
            <h3>
              <Settings2 size={17} /> Public configuration
            </h3>
            <span>READ ONLY</span>
          </div>
          {config.loading ? (
            <Loading label="Loading settings" />
          ) : config.error ? (
            <ErrorState error={config.error} retry={config.reload} />
          ) : (
            <dl className="settings-list">
              {Object.entries(config.data || {}).map(([key, value]) => (
                <div key={key}>
                  <dt>{labels[key] || key.replaceAll("_", " ")}</dt>
                  <dd>
                    <Value value={value} />
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </section>
        <section className="card settings-card">
          <div className="panel-title">
            <h3>
              <Server size={17} /> Runtime health
            </h3>
            <span>LIVE</span>
          </div>
          {health.loading ? (
            <Loading label="Checking services" />
          ) : health.error ? (
            <ErrorState error={health.error} retry={health.reload} />
          ) : (
            <dl className="settings-list">
              {Object.entries(health.data || {}).map(([key, value]) => (
                <div key={key}>
                  <dt>{labels[key] || key.replaceAll("_", " ")}</dt>
                  <dd>
                    <Value value={value} />
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      </div>
      <div className="card settings-explainer">
        <Sparkles size={20} />
        <div>
          <h3>Know which mode you’re using</h3>
          <p>
            Offline mode uses deterministic feature-hash embeddings and
            extractive source summaries. An API-configured generation or
            embedding provider can be enabled independently on the backend.
            Sandbox commands require an available Docker daemon.
          </p>
        </div>
      </div>
    </main>
  );
  return standalone ? (
    <div className="standalone-settings">
      <header className="landing-nav">
        <Logo />
        <Link className="button secondary small" href="/dashboard">
          <ArrowLeft size={14} /> Workspace
        </Link>
      </header>
      {body}
    </div>
  ) : (
    body
  );
}

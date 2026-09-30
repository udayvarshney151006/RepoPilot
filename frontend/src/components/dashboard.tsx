"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  FileArchive,
  FolderGit2,
  Github,
  Plus,
  Search,
  Settings2,
  Upload,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate, useResource } from "@/lib/hooks";
import {
  Badge,
  EmptyState,
  ErrorState,
  Logo,
  Modal,
  PageHeading,
  SkeletonCards,
  ThemeToggle,
} from "./ui";

export function ImportDialog({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const router = useRouter();
  const [method, setMethod] = useState("github");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  async function importRepo(action: () => ReturnType<typeof api.demo>) {
    setBusy(true);
    setError(null);
    try {
      const repo = await action();
      onImported();
      onClose();
      router.push(`/repositories/${repo.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Repository import failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Connect a repository" onClose={onClose}>
      <div className="modal-content">
        <p className="muted mb-5">
          Give your workspace some code to work with.
        </p>
        <div className="segmented">
          <button
            className={method === "github" ? "active" : ""}
            onClick={() => setMethod("github")}
          >
            <Github size={15} /> Public GitHub
          </button>
          <button
            className={method === "zip" ? "active" : ""}
            onClick={() => setMethod("zip")}
          >
            <FileArchive size={15} /> ZIP upload
          </button>
        </div>
        {method === "github" ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void importRepo(() => api.import(url));
            }}
          >
            <label className="field-label" htmlFor="repository-url">
              Repository URL
            </label>
            <input
              id="repository-url"
              type="url"
              required
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              autoFocus
            />
            <p className="field-help">
              Public repositories only. Indexing runs in the background.
            </p>
            <button
              className="button primary full mt-5"
              disabled={busy || !url.trim()}
            >
              {busy ? "Connecting…" : "Connect repository"}
              <ArrowRight size={15} />
            </button>
          </form>
        ) : (
          <div>
            <input
              ref={fileRef}
              type="file"
              accept=".zip,application/zip"
              className="hidden"
              aria-label="Upload repository ZIP"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void importRepo(() => api.upload(file));
              }}
            />
            <button
              className="upload-zone"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              <Upload size={24} />
              <strong>
                {busy ? "Uploading repository…" : "Choose a repository ZIP"}
              </strong>
              <span>
                Source files are filtered and checked before indexing.
              </span>
            </button>
          </div>
        )}
        {error && <ErrorState error={error} />}
        <div className="modal-divider">
          <span>or start exploring</span>
        </div>
        <button
          className="demo-option"
          disabled={busy}
          onClick={() => void importRepo(api.demo)}
        >
          <div className="demo-icon">
            <FolderGit2 size={21} />
          </div>
          <div>
            <strong>Try the demo repository</strong>
            <p>Checkout + authentication, with a reproducible bug.</p>
          </div>
          <ArrowRight size={17} />
        </button>
      </div>
    </Modal>
  );
}
export function Dashboard() {
  const repos = useResource(api.repositories, [], 2500);
  const [importOpen, setImportOpen] = useState(false);
  const [filter, setFilter] = useState("");
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("import"))
      setImportOpen(true);
  }, []);
  const list = (repos.data || []).filter((r) =>
    r.name.toLowerCase().includes(filter.toLowerCase()),
  );
  const ready = (repos.data || []).filter((r) => r.status === "ready");
  return (
    <div className="dashboard-shell">
      <aside className="dashboard-sidebar">
        <Logo />
        <div className="workspace-label">PERSONAL WORKSPACE</div>
        <Link className="nav-item active" href="/dashboard">
          <FolderGit2 size={17} /> Repositories{" "}
          <span className="nav-count">{repos.data?.length ?? "—"}</span>
        </Link>
        <Link className="nav-item" href="/settings">
          <Settings2 size={17} /> Settings
        </Link>
        <div className="sidebar-bottom">
          <span className="local-user">UV</span>
          <div>
            <strong>Local workspace</strong>
            <span>Your repositories, your context</span>
          </div>
          <ThemeToggle />
        </div>
      </aside>
      <div className="dashboard-main">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span>/</span>
            <strong>Repositories</strong>
          </div>
          <div className="topbar-right">
            <span className="local-pill">LOCAL WORKSPACE</span>
            <span className="mobile-theme">
              <ThemeToggle />
            </span>
          </div>
        </header>
        <main className="page dashboard-page">
          <PageHeading
            eyebrow="YOUR WORKSPACE"
            title="Repositories"
            description="A little context changes everything. Start with your code."
            action={
              <button
                className="button primary"
                onClick={() => setImportOpen(true)}
              >
                <Plus size={16} /> Connect repository
              </button>
            }
          />
          <div className="workspace-summary">
            <div>
              <span>Repositories</span>
              <strong>{repos.data?.length ?? "—"}</strong>
            </div>
            <div>
              <span>Ready to explore</span>
              <strong>
                {repos.data ? ready.length : "—"}
                <span className="status-dot green-dot" />
              </strong>
            </div>
            <div>
              <span>Indexed code chunks</span>
              <strong>
                {repos.data
                  ? repos.data
                      .reduce((sum, r) => sum + r.chunk_count, 0)
                      .toLocaleString()
                  : "—"}
              </strong>
            </div>
          </div>
          <div className="section-toolbar">
            <div className="section-label">
              <FolderGit2 size={16} /> All repositories{" "}
              <span>{repos.data?.length ?? "—"}</span>
            </div>
            <div className="search-input">
              <Search size={15} />
              <input
                placeholder="Find a repository…"
                aria-label="Find a repository"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              {filter && (
                <button aria-label="Clear search" onClick={() => setFilter("")}>
                  <X size={13} />
                </button>
              )}
            </div>
          </div>
          {repos.error && (
            <ErrorState error={repos.error} retry={repos.reload} />
          )}{" "}
          {repos.loading ? (
            <SkeletonCards />
          ) : list.length ? (
            <div className="repo-grid">
              {list.map((r) => (
                <Link
                  className="card repository-card"
                  href={`/repositories/${r.id}`}
                  key={r.id}
                >
                  <div className="repo-card-top">
                    <span className="repo-icon">
                      <FolderGit2 size={20} />
                    </span>
                    <Badge status={r.status} />
                  </div>
                  <h3>{r.name}</h3>
                  <p className="repo-url">
                    {r.source_url || "Local source repository"}
                  </p>
                  <div className="repo-card-meta">
                    <span>{r.file_count} files</span>
                    <span>{r.chunk_count} chunks</span>
                    <span>
                      {Array.isArray(r.languages)
                        ? r.languages.slice(0, 2).join(", ")
                        : Object.keys(r.languages || {})
                            .slice(0, 2)
                            .join(", ") || "Pending index"}
                    </span>
                  </div>
                  <div className="repo-card-footer">
                    <span>Added {formatDate(r.created_at)}</span>
                    <span>
                      Open workspace <ArrowUpRight size={13} />
                    </span>
                  </div>
                </Link>
              ))}
              <button
                className="add-repo-card"
                onClick={() => setImportOpen(true)}
              >
                <Plus size={23} />
                <strong>Connect another repository</strong>
                <span>GitHub URL or local ZIP</span>
              </button>
            </div>
          ) : (
            <EmptyState
              icon={<FolderGit2 size={27} />}
              title={
                filter
                  ? "No matching repositories"
                  : "Your next investigation starts here"
              }
              action={
                !filter && (
                  <button
                    className="button primary"
                    onClick={() => setImportOpen(true)}
                  >
                    <Plus size={15} /> Connect repository
                  </button>
                )
              }
            >
              {filter
                ? "Try another name to find your repository."
                : "Connect a public repository, upload your source, or try the included demo."}
            </EmptyState>
          )}
          <div className="workspace-note">
            <div className="note-mark">
              <CodeIcon />
            </div>
            <div>
              <strong>Evidence is always one click away.</strong>
              <p>
                Every answer is grounded in retrieved code. Follow its
                citations, inspect dependencies, and review changes before they
                land.
              </p>
            </div>
          </div>
        </main>
      </div>
      {importOpen && (
        <ImportDialog
          onClose={() => setImportOpen(false)}
          onImported={() => void repos.reload()}
        />
      )}
    </div>
  );
}
function CodeIcon() {
  return <span className="mono">&lt;/&gt;</span>;
}

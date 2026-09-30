"use client";
import { useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Code2,
  FileCode2,
  Folder,
  Files,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { CodeViewer } from "./code-viewer";
import { EmptyState, ErrorState, Loading, PageHeading } from "./ui";

export function FileExplorer({ id }: { id: string }) {
  const files = useResource(() => api.files(id), [id]);
  const [path, setPath] = useState("");
  const [search, setSearch] = useState("");
  const [line, setLine] = useState<number | undefined>();
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const file = useResource(
    () => (path ? api.file(id, path) : Promise.resolve(null)),
    [id, path],
  );
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const selected = params.get("path");
    if (selected) {
      setPath(selected);
      setLine(Number(params.get("line")) || undefined);
    }
  }, []);
  const visible = (files.data || []).filter((f) =>
    f.path.toLowerCase().includes(search.toLowerCase()),
  );
  const dirs = new Set<string>();
  visible.forEach((f) => {
    const parts = f.path.split("/");
    parts
      .slice(0, -1)
      .forEach((_, i) => dirs.add(parts.slice(0, i + 1).join("/")));
  });
  const entries = [
    ...Array.from(dirs).map((path) => ({ path, folder: true })),
    ...visible.map((f) => ({ path: f.path, folder: false })),
  ].sort((a, b) => a.path.localeCompare(b.path));
  return (
    <main className="files-page">
      <div className="feature-page-header">
        <PageHeading
          title="Files"
          description="Browse the source behind every answer."
        />
        <span className="count-label">
          {files.data?.length ?? "—"} source files
        </span>
      </div>
      {files.error && <ErrorState error={files.error} retry={files.reload} />}
      <div className="file-layout">
        <aside className="file-tree">
          <div className="search-input">
            <Search size={14} />
            <input
              placeholder="Find a file…"
              aria-label="Find a file"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="tree-label">
            <Files size={13} /> SOURCE FILES
          </div>
          {files.loading ? (
            <Loading label="Loading files" />
          ) : !entries.length ? (
            <p className="muted p-5">No source files found.</p>
          ) : (
            entries
              .filter(
                (e) =>
                  !Array.from(collapsed).some((folder) =>
                    e.path.startsWith(folder + "/"),
                  ),
              )
              .map((entry) => {
                const parts = entry.path.split("/");
                const depth = parts.length - 1;
                return (
                  <button
                    title={entry.path}
                    className={`tree-entry ${path === entry.path ? "selected" : ""} ${entry.folder ? "folder" : ""}`}
                    key={entry.path}
                    style={{ paddingLeft: 13 + depth * 14 }}
                    onClick={() => {
                      if (entry.folder)
                        setCollapsed((previous) => {
                          const next = new Set(previous);
                          if (next.has(entry.path)) next.delete(entry.path);
                          else next.add(entry.path);
                          return next;
                        });
                      else {
                        setPath(entry.path);
                        setLine(undefined);
                      }
                    }}
                  >
                    {entry.folder ? (
                      <>
                        {collapsed.has(entry.path) ? (
                          <ChevronRight size={12} />
                        ) : (
                          <ChevronDown size={12} />
                        )}
                        <Folder size={14} />
                      </>
                    ) : (
                      <>
                        <span className="tree-spacer" />
                        <FileCode2 size={14} />
                      </>
                    )}
                    <span>{parts.at(-1)}</span>
                  </button>
                );
              })
          )}
        </aside>
        <section className="file-content">
          {path ? (
            file.loading ? (
              <Loading label="Reading source file" />
            ) : file.error ? (
              <ErrorState error={file.error} retry={file.reload} />
            ) : file.data ? (
              <>
                <CodeViewer
                  content={file.data.content}
                  path={file.data.path}
                  language={file.data.language}
                  startLine={line}
                />
                <div className="symbols-panel">
                  <div className="tiny-label">
                    SYMBOLS · {file.data.symbols.length}
                  </div>
                  <div>
                    {file.data.symbols.map((s) => (
                      <button
                        className="symbol-chip"
                        key={s.name + s.start_line}
                        onClick={() => setLine(s.start_line)}
                      >
                        <Code2 size={12} />
                        {s.name}
                        <span>L{s.start_line}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : null
          ) : (
            <EmptyState
              icon={<FileCode2 size={28} />}
              title="Take a closer look"
            >
              Select a file to inspect source code and parsed symbols.
            </EmptyState>
          )}
        </section>
      </div>
    </main>
  );
}

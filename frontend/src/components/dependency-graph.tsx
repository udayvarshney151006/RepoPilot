"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Expand,
  FileCode2,
  GitBranch,
  Minus,
  Plus,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { EmptyState, ErrorState, Loading, PageHeading } from "./ui";

export function DependencyGraph({ id }: { id: string }) {
  const graph = useResource(() => api.graph(id), [id]);
  const [selected, setSelected] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [filter, setFilter] = useState("");
  const impact = useResource(
    () =>
      selected
        ? api.impact(
            id,
            graph.data?.nodes.find((n) => n.id === selected)?.path || selected,
          )
        : Promise.resolve(null),
    [id, selected, graph.data],
  );
  useEffect(() => {
    if (graph.data?.nodes.length && !selected)
      setSelected(graph.data.nodes[0].id);
  }, [graph.data, selected]);
  const positions = useMemo(() => {
    const nodes = graph.data?.nodes || [];
    const map = new Map<string, { x: number; y: number }>();
    const columns = Math.max(2, Math.ceil(Math.sqrt(nodes.length)));
    nodes.forEach((n, i) => {
      const col = i % columns,
        row = Math.floor(i / columns);
      map.set(n.id, {
        x: 95 + col * (670 / Math.max(1, columns - 1)),
        y:
          80 + row * (440 / Math.max(1, Math.ceil(nodes.length / columns) - 1)),
      });
    });
    return map;
  }, [graph.data]);
  const chosen = graph.data?.nodes.find((n) => n.id === selected);
  const incoming = graph.data?.edges.filter((e) => e.target === selected) || [];
  const outgoing = graph.data?.edges.filter((e) => e.source === selected) || [];
  const linked = new Set([
    ...incoming.map((e) => e.source),
    ...outgoing.map((e) => e.target),
    selected,
  ]);
  const fileLink = (nodeId: string) => {
    const n = graph.data?.nodes.find((n) => n.id === nodeId);
    return (
      <button
        className="relationship-link"
        onClick={() => setSelected(nodeId)}
        key={nodeId}
      >
        <FileCode2 size={13} />
        <span>{n?.path || nodeId}</span>
        <ArrowUpRight size={12} />
      </button>
    );
  };
  return (
    <main className="graph-page">
      <div className="feature-page-header">
        <PageHeading
          title="Dependency graph"
          description="See how files connect and where a change may travel."
        />
        <span className="count-label">
          {graph.data?.nodes.length ?? "—"} files ·{" "}
          {graph.data?.edges.length ?? "—"} imports
        </span>
      </div>
      {graph.error ? (
        <div className="p-6">
          <ErrorState error={graph.error} retry={graph.reload} />
        </div>
      ) : graph.loading ? (
        <Loading label="Mapping import relationships" />
      ) : graph.data?.nodes.length ? (
        <div className="graph-layout">
          <section className="graph-canvas">
            <div className="graph-toolbar">
              <div className="graph-legend">
                <span className="status-dot" /> Selected file
                <span className="edge-legend" /> Imports
              </div>
              <div className="graph-controls">
                <button
                  aria-label="Zoom out"
                  onClick={() => setZoom((z) => Math.max(0.55, z - 0.15))}
                >
                  <Minus size={15} />
                </button>
                <span>{Math.round(zoom * 100)}%</span>
                <button
                  aria-label="Zoom in"
                  onClick={() => setZoom((z) => Math.min(2.3, z + 0.15))}
                >
                  <Plus size={15} />
                </button>
                <button aria-label="Fit graph" onClick={() => setZoom(1)}>
                  <Expand size={15} />
                </button>
              </div>
            </div>
            <div className="graph-search search-input">
              <Search size={14} />
              <input
                aria-label="Find graph node"
                placeholder="Find a file in the graph…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </div>
            <div className="graph-svg-wrap">
              <svg
                viewBox="0 0 860 600"
                aria-label="Repository file import graph"
                role="img"
              >
                <defs>
                  <marker
                    id="arrow"
                    markerWidth="7"
                    markerHeight="7"
                    refX="6"
                    refY="3.5"
                    orient="auto"
                  >
                    <path d="M0 0 L7 3.5 L0 7" fill="currentColor" />
                  </marker>
                </defs>
                <g
                  transform={`translate(430 300) scale(${zoom}) translate(-430 -300)`}
                >
                  {graph.data.edges.map((e, i) => {
                    const a = positions.get(e.source),
                      b = positions.get(e.target);
                    if (!a || !b) return null;
                    const strong =
                      e.source === selected || e.target === selected;
                    return (
                      <path
                        className={`graph-edge ${strong ? "selected" : ""}`}
                        d={`M ${a.x} ${a.y} C ${a.x} ${a.y + 65}, ${b.x} ${b.y - 65}, ${b.x} ${b.y}`}
                        markerEnd="url(#arrow)"
                        key={e.source + e.target + i}
                      />
                    );
                  })}
                  {graph.data.nodes.map((n) => {
                    const p = positions.get(n.id)!;
                    const isSelected = n.id === selected;
                    const dim =
                      (selected && !linked.has(n.id)) ||
                      (filter &&
                        !n.path.toLowerCase().includes(filter.toLowerCase()));
                    return (
                      <g
                        key={n.id}
                        className={`graph-node ${isSelected ? "selected" : ""} ${dim ? "dim" : ""}`}
                        transform={`translate(${p.x},${p.y})`}
                        role="button"
                        tabIndex={0}
                        aria-label={`Inspect ${n.path}`}
                        onClick={() => setSelected(n.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ")
                            setSelected(n.id);
                        }}
                      >
                        <title>{n.path}</title>
                        <rect x="-76" y="-23" width="152" height="46" rx="8" />
                        <path d="M-60 -6 h9 l4 4 v10 h-13 z M-51 -6 v4 h4" />
                        <text x="-37" y="-1">
                          {n.path.split("/").at(-1)?.slice(0, 19)}
                        </text>
                        <text className="graph-node-language" x="-37" y="13">
                          {n.language}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>
            </div>
            <div className="graph-footer">
              <GitBranch size={13} /> Conservative file import analysis
              <span>Click any node to inspect its connections</span>
            </div>
          </section>
          <aside className="graph-details">
            <div className="graph-detail-heading">
              <span className="tiny-label">SELECTED FILE</span>
              <h3>
                <FileCode2 size={17} />
                {chosen?.path}
              </h3>
              <Link
                href={`/repositories/${id}/files?path=${encodeURIComponent(chosen?.path || "")}`}
                className="button secondary small"
              >
                Open source <ArrowUpRight size={12} />
              </Link>
            </div>
            <div className="relationship-section">
              <h4>
                <ArrowDownLeft size={14} /> Imported by{" "}
                <span>{incoming.length}</span>
              </h4>
              {incoming.length ? (
                incoming.map((e) => fileLink(e.source))
              ) : (
                <p className="muted">No resolved incoming imports.</p>
              )}
            </div>
            <div className="relationship-section">
              <h4>
                <ArrowUpRight size={14} /> Imports{" "}
                <span>{outgoing.length}</span>
              </h4>
              {outgoing.length ? (
                outgoing.map((e) => fileLink(e.target))
              ) : (
                <p className="muted">No resolved outgoing imports.</p>
              )}
            </div>
            <div className="impact-section">
              <h4>Potential change impact</h4>
              {impact.loading ? (
                <Loading label="Tracing dependents" />
              ) : impact.error ? (
                <ErrorState error={impact.error} />
              ) : impact.data ? (
                <>
                  <div className="impact-count">
                    <strong>{impact.data.affected_files.length}</strong>
                    <span>potentially affected files</span>
                  </div>
                  <p>{impact.data.explanation}</p>
                  {impact.data.affected_files.map((path) => (
                    <Link
                      className="relationship-link"
                      key={path}
                      href={`/repositories/${id}/files?path=${encodeURIComponent(path)}`}
                    >
                      <FileCode2 size={12} />
                      {path}
                    </Link>
                  ))}
                </>
              ) : null}
            </div>
            <div className="graph-limitations">
              <span className="tiny-label">ANALYSIS LIMITS</span>
              <p>
                {Array.isArray(graph.data.limitations)
                  ? graph.data.limitations.join(" ")
                  : graph.data.limitations}
              </p>
            </div>
          </aside>
        </div>
      ) : (
        <EmptyState
          icon={<GitBranch size={28} />}
          title="No dependency graph yet"
        >
          Index a repository to inspect resolved file imports.
        </EmptyState>
      )}
    </main>
  );
}

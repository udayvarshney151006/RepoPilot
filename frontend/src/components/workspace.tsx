"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, type ReactNode } from "react";
import {
  ArrowLeft,
  Bot,
  ChevronDown,
  Files,
  FolderGit2,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Settings2,
  ShieldCheck,
  Activity,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import type { Repository } from "@/lib/types";
import { Badge, ErrorState, Loading, Logo, ThemeToggle } from "./ui";

const RepoContext = createContext<{
  repository: Repository | null;
  reload: () => Promise<void>;
}>({ repository: null, reload: async () => {} });
export const useRepository = () => useContext(RepoContext);
const navigation = [
  { slug: "", label: "Overview", icon: LayoutDashboard },
  { slug: "ask", label: "Ask Repo", icon: MessageSquare },
  { slug: "files", label: "Files", icon: Files },
  { slug: "dependencies", label: "Dependency graph", icon: GitBranch },
  { slug: "agent", label: "Agent", icon: Bot },
  { slug: "evaluations", label: "Evaluations", icon: Activity },
  { slug: "settings", label: "Settings", icon: Settings2 },
];
export function Workspace({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  const repo = useResource(() => api.repository(id), [id], 3000);
  const pathname = usePathname();
  const current = navigation.find(
    (n) => pathname === `/repositories/${id}${n.slug ? "/" + n.slug : ""}`,
  );
  return (
    <RepoContext.Provider
      value={{ repository: repo.data, reload: repo.reload }}
    >
      <div className="workspace-shell">
        <aside className="workspace-sidebar">
          <Logo />
          <Link className="back-link" href="/dashboard">
            <ArrowLeft size={14} /> All repositories
          </Link>
          <div className="repo-switcher">
            <span className="repo-icon">
              <FolderGit2 size={18} />
            </span>
            <div>
              <strong>{repo.data?.name || "Loading repository…"}</strong>
              <span>
                {repo.data
                  ? `${repo.data.file_count} files · ${repo.data.chunk_count} chunks`
                  : "Connecting to workspace"}
              </span>
            </div>
            <ChevronDown size={14} />
          </div>
          <div className="workspace-label">REPOSITORY</div>
          <nav>
            {navigation.map((n) => (
              <Link
                key={n.slug}
                className={`nav-item ${current?.slug === n.slug ? "active" : ""}`}
                href={`/repositories/${id}${n.slug ? "/" + n.slug : ""}`}
              >
                <n.icon size={17} />
                {n.label}
                {n.slug === "agent" && <span className="nav-new">TOOLS</span>}
              </Link>
            ))}
          </nav>
          <div className="sidebar-context">
            <ShieldCheck size={16} />
            <strong>Grounded in your code</strong>
            <p>
              Inspect sources.
              <br />
              Approve every change.
            </p>
          </div>
          <div className="sidebar-bottom">
            <span className="local-user">RP</span>
            <div>
              <strong>Local workspace</strong>
              <span>Developer environment</span>
            </div>
            <ThemeToggle />
          </div>
        </aside>
        <div className="workspace-main">
          <header className="topbar">
            <div className="breadcrumb">
              <Link href="/dashboard">Repositories</Link>
              <span>/</span>
              <strong>{repo.data?.name || "Repository"}</strong>
              <span>/</span>
              <span>{current?.label}</span>
            </div>
            <div className="topbar-right">
              {repo.data && <Badge status={repo.data.status} />}
              <span className="mobile-theme">
                <ThemeToggle />
              </span>
            </div>
          </header>
          <nav className="mobile-nav">
            {navigation.map((n) => (
              <Link
                key={n.slug}
                className={current?.slug === n.slug ? "active" : ""}
                href={`/repositories/${id}${n.slug ? "/" + n.slug : ""}`}
              >
                <n.icon size={15} />
                {n.label}
              </Link>
            ))}
          </nav>
          {repo.error ? (
            <main className="page">
              <ErrorState error={repo.error} retry={repo.reload} />
            </main>
          ) : repo.loading ? (
            <Loading />
          ) : (
            children
          )}
        </div>
      </div>
    </RepoContext.Provider>
  );
}

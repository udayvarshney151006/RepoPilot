"use client";
import Link from "next/link";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  ChevronRight,
  Loader2,
  Moon,
  Sun,
  Terminal,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link className="logo" href="/">
      <span className="logo-mark">
        <Terminal size={19} />
      </span>
      {!compact && (
        <span>
          Repo<span className="logo-light">Pilot</span>
        </span>
      )}
    </Link>
  );
}
export function ThemeToggle() {
  const [theme, setTheme] = useState("dark");
  useEffect(() => {
    const saved = localStorage.getItem("repopilot-theme") || "dark";
    setTheme(saved);
    document.documentElement.dataset.theme = saved;
    const synchronize = () =>
      setTheme(document.documentElement.dataset.theme || "dark");
    window.addEventListener("repopilot-theme", synchronize);
    return () => window.removeEventListener("repopilot-theme", synchronize);
  }, []);
  return (
    <button
      className="icon-button"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      onClick={() => {
        const next =
          document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        setTheme(next);
        localStorage.setItem("repopilot-theme", next);
        document.documentElement.dataset.theme = next;
        window.dispatchEvent(new Event("repopilot-theme"));
      }}
    >
      {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}
export function Badge({ status }: { status: string }) {
  const active = ["ready", "completed", "approved", "healthy"].includes(status),
    failed = ["failed", "rejected", "unavailable"].includes(status);
  return (
    <span className={`badge ${active ? "green" : failed ? "red" : "amber"}`}>
      <span className="status-dot" />
      {status.replaceAll("_", " ")}
    </span>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: string;
  retry?: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={18} />
      <div>
        <strong>Something needs your attention</strong>
        <p>{error}</p>
      </div>
      {retry && (
        <button className="button secondary small" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{icon}</span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Loading({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <Loader2 size={19} className="spin" />
      {label}
    </div>
  );
}
export function SkeletonCards() {
  return (
    <div className="repo-grid">
      {[1, 2, 3].map((n) => (
        <div className="card skeleton-card" key={n}>
          <div className="skeleton w-1/2" />
          <div className="skeleton w-3/4" />
          <div className="skeleton w-full" />
        </div>
      ))}
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const dialog = useRef<HTMLElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") close.current();
      if (e.key === "Tab") {
        const targets = dialog.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]',
        );
        if (!targets?.length) return;
        const first = targets[0],
          last = targets[targets.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (!dialog.current?.contains(document.activeElement))
      dialog.current
        ?.querySelector<HTMLElement>("button, input, textarea")
        ?.focus();
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = previous;
      previousFocus?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={dialog}
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="modal-header">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
export function PanelLink({
  href,
  icon,
  title,
  children,
}: {
  href: string;
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <Link className="card panel-link" href={href}>
      <div className="panel-link-heading">
        {icon}
        <ArrowUpRight size={17} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </Link>
  );
}
export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="button secondary small"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check size={13} /> : null}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}
export function Breadcrumb({ children }: { children: ReactNode }) {
  return (
    <div className="breadcrumb">
      <Link href="/dashboard">Workspace</Link>
      <ChevronRight size={12} />
      {children}
    </div>
  );
}

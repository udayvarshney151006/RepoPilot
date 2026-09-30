import Link from "next/link";
import {
  ArrowRight,
  Check,
  Code2,
  GitBranch,
  Layers3,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react";
import { Logo, ThemeToggle } from "@/components/ui";

export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <Logo />
        <nav>
          <a href="#how-it-works">How it works</a>
          <a href="#built-for-developers">Capabilities</a>
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link className="button secondary small" href="/dashboard">
            Open workspace <ArrowRight size={14} />
          </Link>
        </div>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="pill">
              <span className="status-dot" /> YOUR CODEBASE. IN CONTEXT.
            </div>
            <h1>
              Less searching.
              <br />
              More <span>understanding.</span>
            </h1>
            <p>
              Navigate unfamiliar code, trace dependencies, and investigate bugs
              with AI that shows its sources.
            </p>
            <div className="hero-actions">
              <Link href="/dashboard?import=1" className="button primary large">
                Connect repository <ArrowRight size={17} />
              </Link>
              <Link href="/dashboard" className="button secondary large">
                Explore the workspace
              </Link>
            </div>
            <div className="hero-checks">
              <span>
                <Check size={13} /> Source-grounded answers
              </span>
              <span>
                <Check size={13} /> You approve every patch
              </span>
            </div>
          </div>
          <div
            className="hero-visual"
            aria-label="Code intelligence pipeline illustration"
          >
            <div className="terminal-bar">
              <div className="window-dots">
                <i />
                <i />
                <i />
              </div>
              <span>repository → understanding</span>
              <Terminal size={14} />
            </div>
            <div className="pipeline-preview">
              <div className="preview-source">
                <Code2 size={24} />
                <div>
                  <strong>Your repository</strong>
                  <span>Functions · classes · imports</span>
                </div>
                <span className="file-label">SOURCE</span>
              </div>
              <div className="pipeline-connector" />
              <div className="preview-retrieval">
                <div>
                  <Search size={17} />
                  <span>BM25 search</span>
                </div>
                <span>+</span>
                <div>
                  <Layers3 size={17} />
                  <span>Vector retrieval</span>
                </div>
              </div>
              <div className="pipeline-connector" />
              <div className="preview-rerank">
                <span className="status-dot" /> Fuse & rerank the evidence{" "}
                <GitBranch size={16} />
              </div>
              <div className="pipeline-connector" />
              <div className="preview-answer">
                <Sparkles size={18} />
                <div>
                  <strong>An answer you can inspect.</strong>
                  <p>Relevant code. Clickable citations. Reviewable changes.</p>
                </div>
              </div>
              <div className="preview-bottom">
                <ShieldCheck size={14} /> Repository content is evidence, never
                instructions.
              </div>
            </div>
          </div>
        </section>
        <section className="landing-strip">
          <span>A complete code intelligence workflow</span>
          <div>
            <Code2 size={16} /> Code-aware indexing
          </div>
          <div>
            <Search size={16} /> Hybrid retrieval
          </div>
          <div>
            <GitBranch size={16} /> Dependency analysis
          </div>
          <div>
            <ShieldCheck size={16} /> Human approval
          </div>
        </section>
        <section id="built-for-developers" className="landing-features">
          <div className="section-intro">
            <span className="eyebrow">BUILT FOR THE WORK</span>
            <h2>
              Go from “where is it?”
              <br />
              to “here’s how it works.”
            </h2>
            <p>
              Bring the investigation, the evidence, and the proposed fix into
              one workspace.
            </p>
          </div>
          <div className="feature-grid">
            {[
              {
                icon: Search,
                title: "Answers, with receipts",
                text: "Search identifiers and code meaning together. Open every citation at its exact source lines.",
              },
              {
                icon: GitBranch,
                title: "Follow the connections",
                text: "Explore file imports and their dependents. Understand the potential impact of a change.",
              },
              {
                icon: Terminal,
                title: "An investigation you can follow",
                text: "Inspect each agent tool call, execution result, and proposed diff before approving a change.",
              },
              {
                icon: Layers3,
                title: "Measure what actually works",
                text: "Run a retrieval benchmark and compare vector, lexical, hybrid, and reranked search.",
              },
            ].map((f) => (
              <div className="feature" key={f.title}>
                <f.icon size={21} />
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </div>
            ))}
          </div>
        </section>
        <section id="how-it-works" className="landing-workflow">
          <span className="eyebrow">FROM SOURCE TO CONTEXT</span>
          <h2>One repository. A clearer picture.</h2>
          <div className="workflow-steps">
            {[
              [
                "01",
                "Connect",
                "Import a public GitHub repository or upload a ZIP.",
              ],
              [
                "02",
                "Index",
                "Parse symbols, embed code, and build import relationships.",
              ],
              [
                "03",
                "Investigate",
                "Ask questions, inspect evidence, and propose a reviewed fix.",
              ],
            ].map(([n, t, d]) => (
              <div key={n}>
                <span>{n}</span>
                <h3>{t}</h3>
                <p>{d}</p>
              </div>
            ))}
          </div>
          <Link className="button primary" href="/dashboard?import=1">
            Start with a repository <ArrowRight size={15} />
          </Link>
        </section>
      </main>
      <footer className="landing-footer">
        <Logo />
        <span>Codebase intelligence, grounded in your code.</span>
        <Link href="/dashboard">
          Open workspace <ArrowRight size={14} />
        </Link>
      </footer>
    </div>
  );
}

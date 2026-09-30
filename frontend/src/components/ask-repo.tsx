"use client";
import { useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Code2,
  Layers3,
  MessageSquare,
  Plus,
  Search,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatMs, strategyName } from "@/lib/hooks";
import type { Citation, QueryResult } from "@/lib/types";
import { useRepository } from "./workspace";
import { Badge, ErrorState, Loading, PageHeading } from "./ui";
import { SourceModal } from "./code-viewer";

type Turn = { question: string; response?: QueryResult; error?: string };
const suggestions = [
  "How does authentication work?",
  "Explain the checkout flow.",
  "Where are tokens validated?",
  "What are the main entry points?",
];
function inline(text: string) {
  return text
    .split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
    .map((part, i) =>
      part.startsWith("`") ? (
        <code key={i}>{part.slice(1, -1)}</code>
      ) : part.startsWith("**") ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : (
        part
      ),
    );
}
function AnswerParagraphs({ text }: { text: string }) {
  return (
    <div className="answer-text">
      {text.split("\n").map((line, i) =>
        /^#{1,4}\s/.test(line) ? (
          <h4 key={i}>{inline(line.replace(/^#{1,4}\s/, ""))}</h4>
        ) : /^[-*]\s/.test(line) ? (
          <p className="answer-list-item" key={i}>
            <span>•</span>
            {inline(line.slice(2))}
          </p>
        ) : /^\d+\.\s/.test(line) ? (
          <p className="answer-list-item" key={i}>
            <span>{line.match(/^\d+\./)?.[0]}</span>
            {inline(line.replace(/^\d+\.\s/, ""))}
          </p>
        ) : line ? (
          <p key={i}>{inline(line)}</p>
        ) : (
          <div className="answer-spacer" key={i} />
        ),
      )}
    </div>
  );
}
function Answer({ text }: { text: string }) {
  const parts = text.split(/```([^\n]*)\n([\s\S]*?)```/g);
  return (
    <div>
      {parts.map((part, i) =>
        i % 3 === 0 ? (
          <AnswerParagraphs text={part} key={i} />
        ) : i % 3 === 1 ? (
          <details className="answer-code-details" key={i}>
            <summary>
              Source excerpt {part.trim() ? `· ${part.trim()}` : ""}
            </summary>
            <pre>
              <code>{parts[i + 1]}</code>
            </pre>
          </details>
        ) : null,
      )}
    </div>
  );
}
export function AskRepo({ id }: { id: string }) {
  const { repository } = useRepository();
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [strategy, setStrategy] = useState("hybrid_rerank");
  const [conversation, setConversation] = useState<string | undefined>();
  const [source, setSource] = useState<Citation | null>(null);
  const [inspecting, setInspecting] = useState<number | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  async function ask(value: string) {
    if (!value.trim() || busy || repository?.status !== "ready") return;
    const q = value.trim();
    setQuestion("");
    setBusy(true);
    setTurns((t) => [...t, { question: q }]);
    setTimeout(
      () => bottom.current?.scrollIntoView({ behavior: "smooth" }),
      100,
    );
    try {
      const response = await api.query(id, q, strategy, conversation);
      setConversation(response.conversation_id);
      setTurns((t) => [...t.slice(0, -1), { question: q, response }]);
    } catch (e) {
      setTurns((t) => [
        ...t.slice(0, -1),
        {
          question: q,
          error:
            e instanceof Error ? e.message : "Could not retrieve an answer.",
        },
      ]);
    } finally {
      setBusy(false);
      setTimeout(
        () => bottom.current?.scrollIntoView({ behavior: "smooth" }),
        100,
      );
    }
  }
  const inspected =
    inspecting !== null ? turns[inspecting]?.response : undefined;
  return (
    <main className="ask-page">
      <div className="ask-heading">
        <PageHeading
          title="Ask Repo"
          description="Answers grounded in your repository’s actual code."
          action={
            <button
              className="button secondary small"
              onClick={() => {
                setTurns([]);
                setConversation(undefined);
                setInspecting(null);
              }}
            >
              <Plus size={14} /> New conversation
            </button>
          }
        />
      </div>
      <div className={`chat-layout ${inspected ? "with-inspector" : ""}`}>
        <div className="chat-column">
          <div className="chat-scroll">
            {turns.length === 0 ? (
              <div className="chat-welcome">
                <span className="welcome-icon">
                  <Sparkles size={26} />
                </span>
                <div className="eyebrow">CONTEXT STARTS WITH A QUESTION</div>
                <h2>What would you like to understand?</h2>
                <p>
                  Trace a flow, find a function, or get oriented.
                  <br />
                  Every answer brings its evidence.
                </p>
                <div className="suggestion-grid">
                  {suggestions.map((q, i) => (
                    <button
                      key={q}
                      onClick={() => void ask(q)}
                      disabled={repository?.status !== "ready"}
                    >
                      <span>
                        {i === 0 ? (
                          <BookOpen size={16} />
                        ) : i === 1 ? (
                          <GitFlow />
                        ) : i === 2 ? (
                          <Search size={16} />
                        ) : (
                          <Code2 size={16} />
                        )}
                      </span>
                      {q}
                      <ArrowUp size={13} />
                    </button>
                  ))}
                </div>
                <div className="chat-context">
                  <Layers3 size={13} />
                  {repository?.chunk_count} indexed chunks<span>·</span>
                  <span className="status-dot green-dot" /> Repository context
                  only
                </div>
              </div>
            ) : (
              <div className="conversation">
                {turns.map((turn, i) => (
                  <article className="conversation-turn" key={i}>
                    <div className="user-message">
                      <span className="avatar user-avatar">YOU</span>
                      <div>
                        <span className="message-label">You</span>
                        <p>{turn.question}</p>
                      </div>
                    </div>
                    <div className="assistant-message">
                      <span className="avatar assistant-avatar">
                        <Sparkles size={16} />
                      </span>
                      <div className="assistant-content">
                        <div className="message-label">
                          RepoPilot{" "}
                          {turn.response && (
                            <span className="answer-mode">
                              {turn.response.mode?.replaceAll("_", " ")}
                            </span>
                          )}
                        </div>
                        {turn.error ? (
                          <ErrorState
                            error={turn.error}
                            retry={() => void ask(turn.question)}
                          />
                        ) : !turn.response ? (
                          <div className="thinking">
                            <span className="pulse-dot" /> Retrieving code and
                            composing an answer…
                          </div>
                        ) : (
                          <>
                            <Answer text={turn.response.answer} />
                            {turn.response.citations.length > 0 && (
                              <div className="citation-section">
                                <div className="tiny-label">
                                  SOURCE CITATIONS ·{" "}
                                  {turn.response.citations.length}
                                </div>
                                <div className="citation-list">
                                  {turn.response.citations.map(
                                    (citation, j) => (
                                      <button
                                        key={citation.chunk_id + j}
                                        className="citation"
                                        onClick={() => setSource(citation)}
                                      >
                                        <span className="citation-index">
                                          {j + 1}
                                        </span>
                                        <div>
                                          <strong>{citation.file_path}</strong>
                                          <span>
                                            {citation.symbol_name || "module"} ·
                                            L{citation.start_line}–
                                            {citation.end_line}
                                          </span>
                                        </div>
                                        <ArrowUp size={13} />
                                      </button>
                                    ),
                                  )}
                                </div>
                              </div>
                            )}
                            <div className="answer-footer">
                              <span>
                                <Clock size={12} />
                                {formatMs(turn.response.metrics.total_ms)}
                              </span>
                              <span>
                                <Layers3 size={12} />
                                {turn.response.metrics.retrieved_chunks} chunks
                              </span>
                              <button
                                className={inspecting === i ? "active" : ""}
                                onClick={() =>
                                  setInspecting(inspecting === i ? null : i)
                                }
                              >
                                Inspect retrieval <ChevronRight size={12} />
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
            <div ref={bottom} />
          </div>
          <div className="composer-wrap">
            {repository?.status !== "ready" && (
              <div className="composer-notice">
                Your repository must finish indexing before you can ask
                questions.
              </div>
            )}
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                void ask(question);
              }}
            >
              <textarea
                ref={textarea}
                rows={2}
                value={question}
                aria-label="Ask your repository"
                placeholder="Ask a question about your codebase…"
                disabled={busy || repository?.status !== "ready"}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void ask(question);
                  }
                }}
              />
              <div className="composer-controls">
                <div className="composer-strategy">
                  <Search size={13} />
                  <select
                    aria-label="Retrieval strategy"
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value)}
                  >
                    {["hybrid_rerank", "hybrid", "bm25", "vector"].map((s) => (
                      <option key={s} value={s}>
                        {strategyName(s)}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={12} />
                </div>
                <div className="flex items-center gap-3">
                  <span className="composer-hint">
                    Enter to ask · Shift+Enter for a new line
                  </span>
                  <button
                    className="send-button"
                    aria-label="Send question"
                    disabled={
                      busy || !question.trim() || repository?.status !== "ready"
                    }
                  >
                    {busy ? (
                      <span className="spin">◌</span>
                    ) : (
                      <ArrowUp size={17} />
                    )}
                  </button>
                </div>
              </div>
            </form>
            <div className="composer-caption">
              <Check size={11} /> Source-grounded. Review the citations to
              verify an answer.
            </div>
          </div>
        </div>
        {inspected && (
          <aside className="retrieval-inspector">
            <div className="inspector-header">
              <div>
                <Search size={16} />
                <h3>Retrieval inspector</h3>
              </div>
              <button
                className="icon-button"
                aria-label="Close retrieval inspector"
                onClick={() => setInspecting(null)}
              >
                <ArrowDown size={15} />
              </button>
            </div>
            <div className="inspector-metrics">
              <div>
                <span>Retrieval</span>
                <strong>{formatMs(inspected.metrics.retrieval_ms)}</strong>
              </div>
              <div>
                <span>Reranking</span>
                <strong>{formatMs(inspected.metrics.reranking_ms)}</strong>
              </div>
              <div>
                <span>Generation</span>
                <strong>{formatMs(inspected.metrics.llm_ms)}</strong>
              </div>
              <div>
                <span>Total</span>
                <strong>{formatMs(inspected.metrics.total_ms)}</strong>
              </div>
            </div>
            <div className="inspector-model">
              <span className="tiny-label">MODEL</span>
              <p>{inspected.metrics.model}</p>
              <span className="muted">
                Tokens: {inspected.metrics.input_tokens ?? "unavailable"} in /{" "}
                {inspected.metrics.output_tokens ?? "unavailable"} out
              </span>
              <span className="muted">
                Cost:{" "}
                {inspected.metrics.estimated_cost == null
                  ? "Unavailable"
                  : `$${inspected.metrics.estimated_cost.toFixed(6)}`}
              </span>
            </div>
            <div className="tiny-label inspector-label">
              RETRIEVED EVIDENCE · {inspected.retrieval.length}
            </div>
            {inspected.retrieval.map((c, i) => (
              <button
                className="retrieval-result"
                key={c.chunk_id + i}
                onClick={() => setSource(c)}
              >
                <div>
                  <span className="citation-index">{i + 1}</span>
                  <span className="score">
                    Score {Number(c.score).toFixed(4)}
                  </span>
                </div>
                <strong>{c.file_path}</strong>
                <span>
                  {c.symbol_name || "module"} · L{c.start_line}–{c.end_line}
                </span>
                <pre>
                  {c.content.slice(0, 310)}
                  {c.content.length > 310 ? "…" : ""}
                </pre>
              </button>
            ))}
          </aside>
        )}
      </div>
      {source && (
        <SourceModal
          id={id}
          path={source.file_path}
          startLine={source.start_line}
          endLine={source.end_line}
          onClose={() => setSource(null)}
        />
      )}
    </main>
  );
}
function GitFlow() {
  return <MessageSquare size={16} />;
}

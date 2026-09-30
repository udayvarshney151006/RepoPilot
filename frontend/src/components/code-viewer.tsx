"use client";
import { useEffect, useRef } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-python";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-json";
import "prismjs/components/prism-bash";
import { Code2 } from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { CopyButton, ErrorState, Loading, Modal } from "./ui";

export function CodeViewer({
  content,
  language,
  path,
  startLine,
  endLine,
}: {
  content: string;
  language: string;
  path: string;
  startLine?: number;
  endLine?: number;
}) {
  const lineRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (startLine)
      lineRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [startLine, path, content]);
  const grammar =
    Prism.languages[language] ||
    Prism.languages[
      (
        {
          py: "python",
          ts: "typescript",
          tsx: "typescript",
          js: "javascript",
          jsx: "javascript",
          sh: "bash",
        } as Record<string, string>
      )[language]
    ];
  const highlighted = grammar
    ? Prism.highlight(content, grammar, language)
    : content
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
  // Prism generates only escaped source text and token spans from trusted grammar definitions.
  return (
    <div className="code-viewer">
      <div className="code-header">
        <div>
          <Code2 size={15} />
          <span>{path}</span>
        </div>
        <div>
          <span className="code-language">{language}</span>
          <CopyButton text={content} />
        </div>
      </div>
      <div className="code-scroll">
        <pre>
          <code>
            {highlighted.split("\n").map((line, i) => {
              const n = i + 1;
              return (
                <div
                  key={i}
                  className={`code-line ${startLine && n >= startLine && n <= (endLine || startLine) ? "highlighted" : ""}`}
                  ref={n === startLine ? lineRef : undefined}
                >
                  <span className="line-number">{n}</span>
                  <span
                    className="line-source"
                    dangerouslySetInnerHTML={{ __html: line || " " }}
                  />
                </div>
              );
            })}
          </code>
        </pre>
      </div>
    </div>
  );
}
export function SourceModal({
  id,
  path,
  startLine,
  endLine,
  onClose,
}: {
  id: string;
  path: string;
  startLine: number;
  endLine: number;
  onClose: () => void;
}) {
  const file = useResource(() => api.file(id, path), [id, path]);
  return (
    <Modal wide title={`${path} · L${startLine}–${endLine}`} onClose={onClose}>
      {file.loading ? (
        <Loading label="Opening source file" />
      ) : file.error ? (
        <div className="modal-content">
          <ErrorState error={file.error} retry={file.reload} />
        </div>
      ) : file.data ? (
        <CodeViewer
          path={path}
          content={file.data.content}
          language={file.data.language}
          startLine={startLine}
          endLine={endLine}
        />
      ) : null}
    </Modal>
  );
}
export function DiffViewer({ diff }: { diff: string }) {
  return (
    <div className="diff-viewer">
      <pre>
        {diff.split("\n").map((line, i) => (
          <div
            className={
              line.startsWith("+++") || line.startsWith("---")
                ? "diff-file"
                : line.startsWith("+")
                  ? "diff-add"
                  : line.startsWith("-")
                    ? "diff-remove"
                    : line.startsWith("@@")
                      ? "diff-hunk"
                      : ""
            }
            key={i}
          >
            <span className="diff-gutter">{i + 1}</span>
            <span>{line || " "}</span>
          </div>
        ))}
      </pre>
    </div>
  );
}

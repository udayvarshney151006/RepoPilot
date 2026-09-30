"use client";
import { useCallback, useEffect, useState } from "react";

export function useResource<T>(
  loader: () => Promise<T>,
  dependencies: unknown[] = [],
  interval = 0,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try {
      const next = await loader();
      setData(next);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setLoading(false);
    }
    // The caller declares resource identity through dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setLoading(true);
    setData(null);
    setError(null);
    const update = async () => {
      try {
        const next = await loader();
        if (!disposed) {
          setData(next);
          setError(null);
        }
      } catch (e) {
        if (!disposed)
          setError(e instanceof Error ? e.message : "Request failed.");
      } finally {
        if (!disposed) setLoading(false);
        if (!disposed && interval) timer = setTimeout(update, interval);
      }
    };
    void update();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, interval]);
  return { data, setData, error, loading, reload };
}
export const formatDate = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
export const formatMs = (value: number | null | undefined) =>
  value == null ? "Unavailable" : `${value.toFixed(1)} ms`;
export const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${Math.round(value * 100)}%`;
export const strategyName = (strategy: string) =>
  ({
    vector: "Vector only",
    bm25: "BM25 only",
    hybrid: "Hybrid",
    hybrid_rerank: "Hybrid + reranker",
  })[strategy] || strategy;

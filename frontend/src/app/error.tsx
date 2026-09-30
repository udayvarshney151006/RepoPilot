"use client";
import { ErrorState } from "@/components/ui";
export default function ErrorPage({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <main className="page">
      <ErrorState
        error={
          error.message || "The workspace encountered an unexpected error."
        }
        retry={reset}
      />
    </main>
  );
}

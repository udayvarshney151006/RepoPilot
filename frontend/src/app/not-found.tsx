import Link from "next/link";
export default function NotFound() {
  return (
    <main className="standalone-empty">
      <span className="eyebrow">404 · Page unavailable</span>
      <h1>Let’s find your way back.</h1>
      <p>This workspace page could not be found.</p>
      <Link className="button primary" href="/dashboard">
        Go to dashboard
      </Link>
    </main>
  );
}

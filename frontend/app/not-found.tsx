import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md pt-16 text-center">
      <p className="num text-5xl font-bold text-accent">404</p>
      <h1 className="mt-2 text-lg font-semibold">Page not found</h1>
      <p className="mt-1 text-sm text-ink-muted">Asset pages use the form /asset?symbol=AAPL.</p>
      <Link href="/" className="btn-ghost mt-4">
        Back to overview
      </Link>
    </div>
  );
}

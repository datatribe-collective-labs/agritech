"use client";

import Link from "next/link";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <section className="notice" role="alert">
      <h1>Could not load this page</h1>
      <p>Something went wrong on our side. Try again in a moment.</p>
      <div className="actions">
        <button className="button" type="button" onClick={reset}>Try again</button>
        <Link className="button ghost" href="/">Choose a city</Link>
      </div>
    </section>
  );
}

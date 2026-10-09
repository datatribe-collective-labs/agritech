"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

/** Shown when the API cannot be reached or is being updated. Tells the person what to do next. */
export function Problem({ status }: { status: number }) {
  const router = useRouter();
  const text =
    status === 0 ? "We could not reach the server. Check your connection and try again."
      : status === 503 ? "The data is being updated. Try again in a few minutes."
        : "Something went wrong on our side. Try again in a moment.";
  return (
    <section className="notice" role="alert">
      <h1>Could not load this page</h1>
      <p>{text}</p>
      <div className="actions">
        <button className="button" type="button" onClick={() => router.refresh()}>Try again</button>
        <Link className="button ghost" href="/">Choose a city</Link>
      </div>
    </section>
  );
}

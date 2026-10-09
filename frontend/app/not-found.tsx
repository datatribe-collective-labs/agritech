import Link from "next/link";

export default function NotFound() {
  return (
    <section className="notice">
      <h1>Not found</h1>
      <p>We could not find that page. It may have moved, or the city or crop name may be spelled differently.</p>
      <div className="actions"><Link className="button" href="/">Choose a city</Link></div>
    </section>
  );
}

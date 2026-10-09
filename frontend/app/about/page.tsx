import Link from "next/link";
import { Trail } from "@/components/Trail";
import { getModelInfo } from "@/lib/api";
import type { ModelInfo } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata = { title: "About the data" };

export default async function AboutPage() {
  let info: ModelInfo | null = null;
  try {
    info = await getModelInfo();
  } catch {
    // The page still explains the data without the test results.
  }
  const share = info?.share_recorded != null ? Math.round(info.share_recorded * 100) : null;

  return (
    <>
      <Trail items={[{ label: "Cities", href: "/" }, { label: "About the data" }]} />
      <Link className="back" href="/">Back to cities</Link>
      <header className="page-head">
        <h1>About the data</h1>
        <p className="sub">What the scores mean, and what they do not.</p>
      </header>
      <section className="panel prose">
        <h2>What a score means</h2>
        <p>Each crop is compared with the crops people have recorded growing near the city. A crop that looks like those has a higher rank. It is a guide to what is likely to suit a place, not a promise of yield.</p>
        <h2>Where the information comes from</h2>
        <ul>
          <li>Crop records: GBIF, within 100 km of each city.</li>
          <li>Soil: the WoSIS soil database. Where a city has no measurement, we show it as not measured instead of guessing.</li>
          <li>Climate: ten-year averages from NASA.</li>
          <li>Companion crops and crop needs: a hand-written list. Every entry shows its source, including when it has not yet been checked against a paper.</li>
        </ul>
        {info?.verdict && (
          <>
            <h2>How well it works</h2>
            <p>{info.verdict}</p>
            <p className="muted">
              {info.rows} crop and city pairs across {info.cities} cities were tested{share !== null ? `; ${share}% of them were recorded nearby` : ""}.
              Each city was scored by a model that had never seen it.
            </p>
          </>
        )}
        {info && info.caveats.length > 0 && (
          <>
            <h2>Keep in mind</h2>
            <ul>{info.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
          </>
        )}
      </section>
    </>
  );
}

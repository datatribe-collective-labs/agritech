import Link from "next/link";
import { evidenceLabel, mechanismLabel, plantHref, safeUrl, sourceNote, MONTHS } from "@/lib/format";
import type { MonthlyClimate, PlantCompanion } from "@/lib/types";

export function Stat({ kind, label, value, note }: { kind: "soil" | "rain" | "frost" | "heat"; label: string; value: string | null; note?: string | null }) {
  return (
    <div className={`stat stat-${kind}`}>
      <dt>{label}</dt>
      <dd className={value === null ? "unknown" : ""}>{value ?? "Not measured"}</dd>
      {note && <dd className="note">{note}</dd>}
    </div>
  );
}

/** Where a fact comes from, in plain words, with a link when there is one. */
export function SourceLine({ text, url }: { text: string | null; url: string | null }) {
  const note = sourceNote(text);
  const href = safeUrl(url);
  const tone = note.checked === true ? "is-checked" : note.checked === false ? "is-open" : "";
  return (
    <p className="source">
      <span className={`src-status ${tone}`}>{note.label}</span>{" "}
      {note.detail}
      {href && <> <a href={href} target="_blank" rel="noopener noreferrer">Read the source</a></>}
    </p>
  );
}

export function CompanionCard({ pair, own, city }: { pair: PlantCompanion; own: string; city: string }) {
  const name = pair.partner_common_name || pair.partner;
  return (
    <article className="pair">
      <header className="pair-head">
        <span className="pair-names"><b>{own}</b><span className="plus" aria-hidden="true">+</span><b>{name}</b></span>
        <span className="badges">
          <span className="tag tag-yes">{pair.relationship === "neutral" ? "Compatible" : "Helps each other"}</span>
          <span className="tag">{evidenceLabel(pair.evidence_level)}</span>
        </span>
      </header>
      <h3>{mechanismLabel(pair.mechanism)}</h3>
      <p className="why">{pair.notes || "No explanation has been written for this pair yet."}</p>
      <SourceLine text={pair.evidence_source} url={pair.source_url} />
      {pair.partner_rank_in_city !== null
        ? <Link className="button ghost small" href={plantHref(city, pair.partner)}>See {name} in {city}</Link>
        : <p className="muted small">{name} has no ranking in {city}.</p>}
    </article>
  );
}

export function YearStrip({ months }: { months: MonthlyClimate[] }) {
  const temps = months.map((m) => m.avg_temp_c).filter((t): t is number => t !== null);
  if (!temps.length) return null;
  const low = Math.min(...temps);
  const span = Math.max(Math.max(...temps) - low, 1);
  const good = months.filter((m) => m.is_good_planting_month).length;
  return (
    <section className="panel" aria-labelledby="year-title">
      <h2 id="year-title">The year here</h2>
      <p className="muted">
        {good ? `${good} month${good === 1 ? " is" : "s are"} good for planting (highlighted).` : "No month meets the planting rule below."}{" "}
        A good planting month is 15 to 35 °C, with no frost and at least 20 mm of rain. Averages over ten years.
      </p>
      <ol className="year" role="list">
        {months.map((m) => (
          <li key={m.month} className={m.is_good_planting_month ? "good" : ""}>
            <span className="bar-wrap">
              <span className="bar" style={{ "--h": `${m.avg_temp_c === null ? 8 : 22 + ((m.avg_temp_c - low) / span) * 78}%` } as React.CSSProperties} />
            </span>
            <span className="t">{m.avg_temp_c === null ? "–" : `${Math.round(m.avg_temp_c)}°`}</span>
            <span className="rain" title="Average rain">{m.avg_monthly_rain_mm === null ? "–" : Math.round(m.avg_monthly_rain_mm)}</span>
            <span className="m">{MONTHS[m.month - 1]}</span>
          </li>
        ))}
      </ol>
      <p className="legend"><span className="dot t" />Temperature (°C) <span className="dot r" />Rain (mm a month)</p>
    </section>
  );
}

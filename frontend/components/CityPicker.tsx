"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { cityHref, countryName, frostLabel } from "@/lib/format";
import type { CitySummary } from "@/lib/types";

const LAST_CITY = "planting.lastCity";

/** The home screen: headline, search box and the city cards. Search runs in the browser, so it is instant. */
export function CityPicker({ cities, art }: { cities: CitySummary[]; art: React.ReactNode }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [last, setLast] = useState<string | null>(null);

  useEffect(() => {
    try { setLast(localStorage.getItem(LAST_CITY)); } catch { /* storage blocked */ }
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? cities.filter((c) => `${c.city} ${countryName(c.country)}`.toLowerCase().includes(q)) : cities;
  }, [cities, query]);
  const again = cities.find((c) => c.city === last);

  return (
    <>
      <section className="hero">
        {art}
        <div className="hero-text">
          <h1>What will grow well where you live?</h1>
          <p className="lede">Choose your city. You will see the crops that suit its soil and climate, and which ones grow well side by side.</p>
          <label className="search">
            <span className="sr-only">Search for your city</span>
            <input
              type="search" placeholder="Search for your city" autoComplete="off" enterKeyHint="go"
              value={query} onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && shown[0]) router.push(cityHref(shown[0].city)); }}
            />
          </label>
          {again && <p className="again">Last time: <Link href={cityHref(again.city)}>{again.city}</Link></p>}
        </div>
      </section>
      <section aria-label="Cities">
        <div className="city-grid">
          {shown.map((c) => (
            <Link key={c.city} className={`city-card ${c.has_recommendations ? "" : "is-quiet"}`} href={cityHref(c.city)}>
              <span className="city-name">{c.city}</span>
              <span className="city-country">{countryName(c.country)}</span>
              <span className="city-meta">{frostLabel(c.frost_zone)}{c.has_recommendations ? "" : " · no crop advice yet"}</span>
            </Link>
          ))}
        </div>
        {shown.length === 0 && (
          <p className="empty" role="status">No city matches that search. Check the spelling, or clear the search to see all {cities.length} cities.</p>
        )}
      </section>
    </>
  );
}

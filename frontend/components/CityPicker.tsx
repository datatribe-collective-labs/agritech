"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { groupByContinent, type Continent } from "@/lib/continents";
import { cityHref, countryName } from "@/lib/format";
import type { CitySummary } from "@/lib/types";

const LAST_CITY = "planting.lastCity";

/**
 * The home screen: headline, search box and the cities, folded under their continents.
 * A continent opens when you click it and closes when you click it again. Typing in the search
 * box opens every continent that has a match. Search runs in the browser, so it is instant.
 */
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

  const groups = useMemo(() => groupByContinent(shown), [shown]);
  const [open, setOpen] = useState<Set<Continent>>(new Set());
  const searching = query.trim() !== "";

  // Open the continent of the city you looked at last time, so "back to my city" is one click.
  useEffect(() => {
    const home = again && groupByContinent([again])[0]?.continent;
    if (home) setOpen((now) => new Set(now).add(home));
  }, [again]);

  const toggle = (continent: Continent) =>
    setOpen((now) => {
      const next = new Set(now);
      if (!next.delete(continent)) next.add(continent);
      return next;
    });

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
      <section aria-label="Cities by continent" className="continents">
        {groups.map((group, index) => {
          const isOpen = searching || open.has(group.continent);
          const id = `continent-${index}`;
          return (
            <div key={group.continent} className={`continent ${isOpen ? "is-open" : ""}`} data-continent={group.continent}>
              <h2 className="continent-head">
                <button type="button" aria-expanded={isOpen} aria-controls={id} onClick={() => toggle(group.continent)}>
                  <span className="continent-badge" aria-hidden="true">{group.cityCount}</span>
                  <span className="continent-label">
                    <span className="continent-name">{group.continent}</span>
                    <span className="continent-count">
                      {group.countries.length} {group.countries.length === 1 ? "country" : "countries"}
                    </span>
                  </span>
                  <span className="chevron" aria-hidden="true" />
                </button>
              </h2>
              <div id={id} className="continent-body" role="region" aria-label={`Cities in ${group.continent}`}>
                <div className="continent-inner" inert={!isOpen}>
                  <div className="continent-content">
                    {group.countries.map((country, i) => (
                      <div key={country.code} className="country" style={{ "--i": i } as React.CSSProperties}>
                        <h3>{country.name}</h3>
                        <ul className="city-pills">
                          {country.cities.map((c) => (
                            <li key={c.city}>
                              <Link className={`city-pill ${c.has_recommendations ? "" : "is-quiet"}`} href={cityHref(c.city)}>
                                {c.city}
                                {!c.has_recommendations && <span className="sr-only"> (no crop advice yet)</span>}
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        {groups.length === 0 && (
          <p className="empty" role="status">No city matches that search. Check the spelling, or clear the search to see all {cities.length} cities.</p>
        )}
        <p className="legend small muted">Dashed cities have no crop advice yet.</p>
      </section>
    </>
  );
}

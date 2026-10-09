"use client";

import Link from "next/link";
import { useState } from "react";
import { groupLabel, plantHref, relativeFit } from "@/lib/format";
import type { CityPlant } from "@/lib/types";

const SHOWN_FIRST = 12;

/** Ranked crops for a city: top 12 first, a button for the rest, and filters by type of crop. */
export function CropList({ city, plants }: { city: string; plants: CityPlant[] }) {
  const [group, setGroup] = useState("");
  const [expanded, setExpanded] = useState(false);
  const best = plants[0]?.suitability_score ?? 0;
  const groups = [...new Set(plants.map((p) => p.functional_group).filter((g): g is string => !!g))].sort();

  const visible = plants.filter((p, i) => (group ? p.functional_group === group : expanded || i < SHOWN_FIRST));
  const canExpand = !group && !expanded && plants.length > SHOWN_FIRST;

  return (
    <>
      <div className="chips" role="group" aria-label="Filter by type of crop">
        <button type="button" className={`chip ${group === "" ? "is-on" : ""}`} aria-pressed={group === ""} onClick={() => setGroup("")}>All</button>
        {groups.map((g) => (
          <button key={g} type="button" className={`chip ${group === g ? "is-on" : ""}`} aria-pressed={group === g} onClick={() => setGroup(g)}>
            {groupLabel(g)}
          </button>
        ))}
      </div>
      <div className="plant-list">
        {visible.map((p) => {
          const share = Math.round(relativeFit(p.suitability_score, best) * 100);
          return (
            <Link key={p.species} className="plant-card" href={plantHref(city, p.species)}>
              <span className="rank" aria-label={`Rank ${p.rank_in_city}`}>{p.rank_in_city}</span>
              <span className="plant-main">
                <span className="plant-name">{p.common_name || p.species}</span>
                <span className="latin">{p.species}</span>
                <span className="tags">
                  {p.functional_group && <span className="tag">{groupLabel(p.functional_group)}</span>}
                  <span className={`tag ${p.observed_nearby ? "tag-yes" : "tag-no"}`}>{p.observed_nearby ? "Recorded nearby" : "Not recorded nearby"}</span>
                </span>
              </span>
              <span className="fit" role="img" aria-label={`Match compared with the best crop here: ${share} percent`}>
                <span className="fit-bar"><i style={{ "--w": `${share}%` } as React.CSSProperties} /></span>
                <span className="fit-label">{p.rank_in_city === 1 ? "Best match here" : `${share}% of the best`}</span>
              </span>
            </Link>
          );
        })}
      </div>
      {canExpand && (
        <p className="more"><button className="button ghost" type="button" onClick={() => setExpanded(true)}>Show all {plants.length} crops</button></p>
      )}
    </>
  );
}

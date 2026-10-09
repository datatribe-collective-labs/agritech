import Link from "next/link";
import { notFound } from "next/navigation";
import { CompanionCard, SourceLine } from "@/components/Parts";
import { Problem } from "@/components/Problem";
import { RememberCity } from "@/components/RememberCity";
import { Trail } from "@/components/Trail";
import { ApiError, getCity, getCompanions, getPlantInCity, statusOf } from "@/lib/api";
import { cityHref, decode, fitChecks, groupLabel, humanize } from "@/lib/format";
import type { CityDetail, CityPlantDetail, PlantCompanion } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ city: string; species: string }> };

export async function generateMetadata({ params }: Props) {
  const { city, species } = await params;
  try {
    const plant = await getPlantInCity(decode(city), decode(species));
    return { title: `${plant.common_name || plant.species} in ${decode(city)}` };
  } catch {
    return { title: decode(species) };
  }
}

const range = (low: number | null, high: number | null, unit = "") => (low === null || high === null ? null : `${low} to ${high}${unit}`);

export default async function PlantPage({ params }: Props) {
  const route = await params;
  const cityName = decode(route.city);
  const species = decode(route.species);

  let data: [CityDetail, CityPlantDetail, PlantCompanion[]];
  try {
    data = await Promise.all([getCity(cityName), getPlantInCity(cityName, species), getCompanions(cityName, species)]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <Problem status={statusOf(error)} />;
  }
  const [city, plant, pairs] = data;
  const own = plant.common_name || plant.species;
  const t = plant.traits;
  const checks = fitChecks(plant.fit, t, city.soil_ph);
  const needs: Array<[string, string | null]> = [
    ["Soil pH", range(t.optimal_ph_min, t.optimal_ph_max)],
    ["Temperature", range(t.optimal_temp_min_c, t.optimal_temp_max_c, " °C")],
    ["Time to mature", range(t.days_to_maturity_min, t.days_to_maturity_max, " days")],
    ["Water need", humanize(t.water_demand) || null],
    ["Drought tolerance", humanize(t.drought_tolerance) || null],
    ["Frost", t.frost_hardy === null ? null : t.frost_hardy ? "Frost hardy" : "Not frost hardy"],
    ["Role for the soil", humanize(t.nitrogen_role) || null],
  ];

  return (
    <>
      <Trail items={[{ label: "Cities", href: "/" }, { label: city.city, href: cityHref(city.city) }, { label: own }]} />
      <RememberCity city={city.city} />
      <Link className="back" href={cityHref(city.city)}>Back to crops for {city.city}</Link>
      <header className="page-head">
        <h1>{own}</h1>
        <p className="sub"><span className="latin">{plant.species}</span>{plant.functional_group ? ` · ${groupLabel(plant.functional_group)}` : ""}</p>
        <p className="tags">
          <span className="tag">Rank {plant.rank_in_city} in {city.city}</span>
          <span className={`tag ${plant.observed_nearby ? "tag-yes" : "tag-no"}`}>{plant.observed_nearby ? "Recorded nearby" : "Not recorded nearby"}</span>
        </p>
      </header>

      <section className="panel" aria-labelledby="pairs-title">
        <h2 id="pairs-title">Grows well with</h2>
        {pairs.length ? (
          <>
            <p className="muted">Crops that help {own} when planted close by, and why. Only crops recorded near {city.city} are listed.</p>
            <div className="pairs">
              {pairs.map((pair) => <CompanionCard key={pair.partner} pair={pair} own={own} city={city.city} />)}
            </div>
          </>
        ) : (
          <p className="empty-inline">
            No companion crop is listed for {own} near {city.city}. Our companion list is written by hand and is still short,
            so this does not mean {own} has no good partners.
          </p>
        )}
      </section>

      <section className="panel two" aria-labelledby="rank-title">
        <div>
          <h2 id="rank-title">How {own} fits {city.city}</h2>
          <ul className="checks">
            {checks.map((c) => (
              <li key={c.text} className={c.ok === true ? "yes" : c.ok === false ? "no" : "maybe"}>
                <span className="mark" aria-hidden="true" />
                <span><span className="sr-only">{c.ok === true ? "Good: " : c.ok === false ? "Problem: " : "Unknown: "}</span>{c.text}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2>What the model weighed</h2>
          {plant.reasons.length
            ? <ol className="reasons">{plant.reasons.map((r) => <li key={r.rank}>{r.text}</li>)}</ol>
            : <p className="muted">No single factor stood out for this crop.</p>}
          <p className="muted small">These show how the model scored this crop. They are not proof of what makes it grow.</p>
        </div>
      </section>

      <section className="panel" aria-labelledby="needs-title">
        <h2 id="needs-title">What {own} needs</h2>
        <dl className="needs">
          {needs.map(([label, value]) => (
            <div key={label}><dt>{label}</dt><dd className={value === null ? "unknown" : ""}>{value ?? "Not known"}</dd></div>
          ))}
        </dl>
        {t.notes && <p className="muted">{t.notes}</p>}
        <SourceLine text={t.trait_source} url={t.source_url} />
      </section>
    </>
  );
}

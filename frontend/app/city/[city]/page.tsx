import Link from "next/link";
import { notFound } from "next/navigation";
import { CropList } from "@/components/CropList";
import { Problem } from "@/components/Problem";
import { RememberCity } from "@/components/RememberCity";
import { Stat, YearStrip } from "@/components/Parts";
import { Trail } from "@/components/Trail";
import { ApiError, getCity, getCityMonths, getCityPlants, statusOf } from "@/lib/api";
import { countryName, decode, frostLabel, humanize, number } from "@/lib/format";
import type { CityDetail, CityPlants, MonthlyClimate } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ city: string }> };

export async function generateMetadata({ params }: Props) {
  return { title: decode((await params).city) };
}

export default async function CityPage({ params }: Props) {
  const name = decode((await params).city);
  let data: [CityDetail, CityPlants, MonthlyClimate[]];
  try {
    data = await Promise.all([getCity(name), getCityPlants(name), getCityMonths(name)]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    return <Problem status={statusOf(error)} />;
  }
  const [city, ranked, months] = data;
  const goodMonths = months.filter((m) => m.is_good_planting_month).length;

  return (
    <>
      <Trail items={[{ label: "Cities", href: "/" }, { label: city.city }]} />
      <RememberCity city={city.city} />
      <Link className="back" href="/">Back to cities</Link>
      <header className="page-head">
        <h1>{city.city}</h1>
        <p className="sub">{countryName(city.country)}</p>
      </header>

      <dl className="stats">
        <Stat kind="soil" label="Soil acidity (pH)" value={number(city.soil_ph, 1)} note={humanize(city.ph_band) || null} />
        <Stat kind="soil" label="Soil type" value={humanize(city.soil_texture_class) || null}
          note={city.clay_pct !== null ? `${number(city.clay_pct, 0)}% clay` : null} />
        <Stat kind="rain" label="Rain a year" value={city.avg_annual_precip_mm !== null ? `${number(city.avg_annual_precip_mm)} mm` : null}
          note={humanize(city.rainfall_band) || null} />
        <Stat kind="frost" label="Frost" value={frostLabel(city.frost_zone)}
          note={city.avg_frost_days_per_year !== null ? `${number(city.avg_frost_days_per_year, 0)} frost days a year` : null} />
        <Stat kind="heat" label="Good planting months" value={months.length ? `${goodMonths} of 12` : null} />
      </dl>

      {ranked.recommendations_available ? (
        <section className="panel" aria-labelledby="crops-title">
          <h2 id="crops-title">Crops for {city.city}</h2>
          <p className="muted">
            Ranked by how closely each crop matches the crops people have recorded near {city.city}. This is a guide, not a yield forecast.
            The bar compares each crop with the best match here. <Link href="/about">How to read this</Link>
          </p>
          <CropList city={city.city} plants={ranked.plants} />
        </section>
      ) : (
        <section className="notice" role="status">
          <h2>No crop advice for {city.city} yet</h2>
          <p>{ranked.message}</p>
          <div className="actions"><Link className="button" href="/">Choose another city</Link></div>
        </section>
      )}

      <YearStrip months={months} />
    </>
  );
}

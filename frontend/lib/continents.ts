// Groups the cities by continent, then by country, for the home screen.
import { countryName } from "./format";
import type { CitySummary } from "./types";

export const CONTINENTS = ["Africa", "Asia", "Europe", "North America", "South America", "Oceania"] as const;
export type Continent = (typeof CONTINENTS)[number] | "Other places";

// Country code -> continent. A country that is not listed here appears under "Other places"
// (and the test in continents.test.ts fails), so a new city is never silently lost.
const CONTINENT_OF: Record<string, Continent> = {
  // Africa
  DZ: "Africa", EG: "Africa", ET: "Africa", GH: "Africa", KE: "Africa", MA: "Africa", NG: "Africa", RW: "Africa",
  SN: "Africa", TZ: "Africa", UG: "Africa", ZA: "Africa", ZM: "Africa", ZW: "Africa", CI: "Africa", CM: "Africa",
  // Asia (Turkey, Iran and Jordan are counted here)
  BD: "Asia", CN: "Asia", ID: "Asia", IN: "Asia", IR: "Asia", JO: "Asia", JP: "Asia", KR: "Asia", KZ: "Asia",
  MY: "Asia", NP: "Asia", PH: "Asia", PK: "Asia", TH: "Asia", TR: "Asia", UZ: "Asia", VN: "Asia", LK: "Asia",
  // Europe
  AT: "Europe", CZ: "Europe", DE: "Europe", DK: "Europe", ES: "Europe", FI: "Europe", FR: "Europe", HU: "Europe",
  IT: "Europe", NO: "Europe", PL: "Europe", RO: "Europe", SE: "Europe", UA: "Europe", GB: "Europe", NL: "Europe",
  PT: "Europe", GR: "Europe", IE: "Europe",
  // North America (including Mexico)
  CA: "North America", MX: "North America", US: "North America",
  // South America
  AR: "South America", BR: "South America", CL: "South America", CO: "South America", PE: "South America",
  PY: "South America", UY: "South America", EC: "South America", BO: "South America",
  // Oceania
  AU: "Oceania", NZ: "Oceania",
};

export const continentOf = (code: string | null | undefined): Continent =>
  (code && CONTINENT_OF[code.toUpperCase()]) || "Other places";

export type CountryGroup = { code: string; name: string; cities: CitySummary[] };
export type ContinentGroup = { continent: Continent; countries: CountryGroup[]; cityCount: number };

/** Continents in a fixed order (empty ones left out), countries A to Z, cities A to Z. */
export function groupByContinent(cities: CitySummary[]): ContinentGroup[] {
  const byContinent = new Map<Continent, Map<string, CountryGroup>>();
  for (const city of cities) {
    const code = (city.country ?? "").toUpperCase();
    const continent = continentOf(code);
    const countries = byContinent.get(continent) ?? new Map<string, CountryGroup>();
    const group = countries.get(code) ?? { code, name: countryName(code) || "Country not stated", cities: [] };
    group.cities.push(city);
    countries.set(code, group);
    byContinent.set(continent, countries);
  }
  const order: Continent[] = [...CONTINENTS, "Other places"];
  return order.flatMap((continent) => {
    const countries = byContinent.get(continent);
    if (!countries) return [];
    const list = [...countries.values()]
      .map((c) => ({ ...c, cities: [...c.cities].sort((a, b) => a.city.localeCompare(b.city)) }))
      .sort((a, b) => a.name.localeCompare(b.name));
    return [{ continent, countries: list, cityCount: list.reduce((n, c) => n + c.cities.length, 0) }];
  });
}

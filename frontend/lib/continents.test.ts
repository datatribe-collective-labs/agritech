import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { continentOf, groupByContinent } from "./continents";
import type { CitySummary } from "./types";

const city = (name: string, country: string | null, has = true): CitySummary => ({
  city: name, country, latitude: null, longitude: null, frost_zone: null, soil_ph: null, has_recommendations: has,
});

describe("grouping cities by continent", () => {
  const groups = groupByContinent([
    city("Nairobi", "KE"), city("Accra", "GH"), city("Obuasi", "GH"), city("Paris", "FR"),
    city("Mexico City", "MX"), city("Atlantis", "ZZ"), city("Nowhere", null),
  ]);

  it("lists continents in a fixed order and leaves empty ones out", () => {
    expect(groups.map((g) => g.continent)).toEqual(["Africa", "Europe", "North America", "Other places"]);
  });

  it("sorts countries and cities A to Z and counts cities", () => {
    const africa = groups[0];
    expect(africa.countries.map((c) => c.name)).toEqual(["Ghana", "Kenya"]);
    expect(africa.countries[0].cities.map((c) => c.city)).toEqual(["Accra", "Obuasi"]);
    expect(africa.cityCount).toBe(3);
  });

  it("puts unknown or missing countries under Other places instead of dropping them", () => {
    expect(groups[3].countries.flatMap((c) => c.cities.map((x) => x.city)).sort()).toEqual(["Atlantis", "Nowhere"]);
    expect(continentOf(undefined)).toBe("Other places");
  });

  it("accepts lower-case codes", () => {
    expect(continentOf("ke")).toBe("Africa");
  });
});

describe("the city list in the repository", () => {
  it("has a continent for every country the pipeline fetches", () => {
    let source = "";
    try { source = readFileSync(join(__dirname, "../../scripts/shared_locations.py"), "utf8"); } catch { return; } // frontend built on its own
    const codes = [...source.matchAll(/"Country":\s*"([A-Z]{2})"/g)].map((m) => m[1]);
    expect(codes.length).toBeGreaterThan(40);
    expect(codes.filter((code) => continentOf(code) === "Other places")).toEqual([]);
  });
});

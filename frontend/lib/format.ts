// Plain-language wording for the API's codes. Pure functions, covered by format.test.ts.

import type { FitChecks, PlantProfile } from "./types";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Path segments arrive percent-encoded; decode them without failing on stray characters. */
export function decode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

export const cityHref = (city: string) => `/city/${encodeURIComponent(city)}`;
export const plantHref = (city: string, species: string) => `${cityHref(city)}/plant/${encodeURIComponent(species)}`;

/** Only web links are allowed as hrefs; anything else is dropped. */
export const safeUrl = (url: string | null | undefined): string | null => (/^https?:\/\//i.test(url ?? "") ? (url as string) : null);

export function humanize(code: string | null | undefined): string {
  if (!code) return "";
  const text = code.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const groupLabel = humanize;

export function countryName(code: string | null | undefined): string {
  if (!code) return "";
  try {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(code.toUpperCase()) ?? code;
  } catch {
    return code;
  }
}

const FROST: Record<string, string> = {
  frost_free: "No frost", light_frost: "Light frost", moderate_frost: "Moderate frost",
  heavy_frost: "Heavy frost", severe_frost: "Severe frost",
};
export const frostLabel = (zone: string | null | undefined) => (zone && FROST[zone]) || humanize(zone) || "Frost unknown";

const MECHANISMS: Record<string, string> = {
  nitrogen_fixation: "Feeds the soil with nitrogen",
  ground_cover: "Shades the soil and keeps it moist",
  root_complementarity: "Roots share the soil without competing",
  canopy_complementarity: "Leaves share the light",
  pest_repulsion: "Keeps pests away",
  predator_attraction: "Attracts helpful insects",
  allelopathy: "Holds back weeds and pests",
  phosphorus_solubilising: "Unlocks phosphorus in the soil",
};
export const mechanismLabel = (code: string | null | undefined) => (code && MECHANISMS[code]) || humanize(code) || "Helps its partner";

const EVIDENCE: Record<string, string> = { scientific: "Backed by research", traditional: "Traditional practice", anecdotal: "Farmer reports" };
export const evidenceLabel = (level: string | null | undefined) => (level && EVIDENCE[level]) || "Evidence not stated";

export function number(value: number | null | undefined, digits = 0): string | null {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return Number(value).toLocaleString("en", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** How full the fit bar is: this crop's score compared with the best crop in the city (0 to 1). */
export const relativeFit = (score: number, best: number) => (best > 0 ? Math.max(0, Math.min(1, score / best)) : 0);

export type FitCheck = { ok: boolean | null; text: string };

/** Plain-language checks of the crop against the city. ok: true / false / null (cannot tell). */
export function fitChecks(fit: FitChecks, traits: PlantProfile | null, soilPh: number | null): FitCheck[] {
  const months = (n: number | null) => `${n} month${n === 1 ? "" : "s"}`;
  const checks: FitCheck[] = [];

  if (fit.enough_warm_months === null) {
    checks.push({ ok: null, text: "We do not have enough temperature data to check warm months." });
  } else {
    checks.push({
      ok: fit.enough_warm_months === 1,
      text: `${months(fit.months_in_optimal_temp)} a year are in its ideal temperature range. It needs about ${months(fit.months_to_mature)} to mature.`,
    });
  }

  if (traits?.frost_hardy) {
    checks.push({ ok: true, text: "It is frost hardy, so frost is not a problem." });
  } else if (fit.enough_frost_free_months === null) {
    checks.push({ ok: null, text: "We do not have enough frost data to check frost-free months." });
  } else {
    checks.push({
      ok: fit.enough_frost_free_months === 1,
      text: `${months(fit.frost_free_months)} a year are frost free. It needs about ${months(fit.months_to_mature)} to mature.`,
    });
  }

  const range = traits && traits.optimal_ph_min !== null && traits.optimal_ph_max !== null
    ? `${traits.optimal_ph_min} to ${traits.optimal_ph_max}` : null;
  if (fit.ph_gap === null) {
    checks.push({ ok: null, text: "Soil acidity could not be compared, because the soil pH or the crop's pH range is missing." });
  } else if (Number(fit.ph_gap) === 0) {
    checks.push({ ok: true, text: `The soil pH (${soilPh}) is inside its ideal range of ${range}.` });
  } else {
    checks.push({ ok: false, text: `The soil pH (${soilPh}) is ${number(fit.ph_gap, 1)} outside its ideal range of ${range}.` });
  }
  return checks;
}

export type SourceNote = { checked: boolean | null; label: string; detail: string };

/** Turns the raw source text of a trait or pair into a plain status plus the readable detail. */
export function sourceNote(text: string | null | undefined): SourceNote {
  const t = (text ?? "").trim();
  if (!t) return { checked: null, label: "Source not stated", detail: "" };
  const clean = (s: string) =>
    s.replace(/\s*See DATA_PROVENANCE\.md\.?/gi, "").replace(/evidence_level/g, "evidence rating")
      .replace(/\s+in this pass/gi, "").replace(/\s{2,}/g, " ").trim();
  if (/^VERIFIED\b/i.test(t)) {
    return { checked: true, label: "Checked against a published source", detail: clean(t.replace(/^VERIFIED\s*[—–-]+\s*/i, "")) };
  }
  if (/not (independently |individually )?(source-)?verified/i.test(t)) {
    return { checked: false, label: "Not yet checked against a paper", detail: clean(t) };
  }
  return { checked: null, label: "Source", detail: clean(t) };
}

// Small, pure helpers: safe HTML templating and plain-language wording for the API's codes.
// Nothing here touches the page, so it can be tested with `node --test frontend/tests`.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export class Raw { constructor(text) { this.text = text; } }
export const raw = (text) => new Raw(text);
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ESCAPES[c]);

function render(value) {
  if (value instanceof Raw) return value.text;
  if (Array.isArray(value)) return value.map(render).join("");
  if (value === false || value === null || value === undefined) return "";
  return esc(value);
}

/** Tagged template: every inserted value is escaped unless it is already html`...` output. */
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((value, i) => { out += render(value) + strings[i + 1]; });
  return new Raw(out);
}

/** Only web links are allowed as hrefs; anything else is dropped. */
export const safeUrl = (url) => (/^https?:\/\//i.test(url || "") ? url : null);

export const humanize = (code) => {
  if (!code) return "";
  const text = String(code).replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

export function countryName(code) {
  if (!code) return "";
  try { return new Intl.DisplayNames(["en"], { type: "region" }).of(code.toUpperCase()) || code; }
  catch { return code; }
}

const FROST = {
  frost_free: "No frost", light_frost: "Light frost", moderate_frost: "Moderate frost",
  heavy_frost: "Heavy frost", severe_frost: "Severe frost",
};
export const frostLabel = (zone) => FROST[zone] || humanize(zone) || "Frost unknown";

const MECHANISMS = {
  nitrogen_fixation: "Feeds the soil with nitrogen",
  ground_cover: "Shades the soil and keeps it moist",
  root_complementarity: "Roots share the soil without competing",
  canopy_complementarity: "Leaves share the light",
  pest_repulsion: "Keeps pests away",
  predator_attraction: "Attracts helpful insects",
  allelopathy: "Holds back weeds and pests",
  phosphorus_solubilising: "Unlocks phosphorus in the soil",
};
export const mechanismLabel = (code) => MECHANISMS[code] || humanize(code) || "Helps its partner";

const EVIDENCE = { scientific: "Backed by research", traditional: "Traditional practice", anecdotal: "Farmer reports" };
export const evidenceLabel = (level) => EVIDENCE[level] || "Evidence not stated";

export const groupLabel = humanize;

export function number(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  return Number(value).toLocaleString("en", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** How full the fit bar is: this crop's score compared with the best crop in the city (0 to 1). */
export const relativeFit = (score, best) => (best > 0 ? Math.max(0, Math.min(1, score / best)) : 0);

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Plain-language checks of the crop against the city. ok: true / false / null (cannot tell). */
export function fitChecks(fit, traits, soilPh) {
  const checks = [];
  const months = (n) => `${n} month${n === 1 ? "" : "s"}`;

  if (fit.enough_warm_months === null || fit.enough_warm_months === undefined) {
    checks.push({ ok: null, text: "We do not have enough temperature data to check warm months." });
  } else {
    checks.push({
      ok: fit.enough_warm_months === 1,
      text: `${months(fit.months_in_optimal_temp)} a year are in its ideal temperature range. It needs about ${months(fit.months_to_mature)} to mature.`,
    });
  }

  if (traits && traits.frost_hardy) {
    checks.push({ ok: true, text: "It is frost hardy, so frost is not a problem." });
  } else if (fit.enough_frost_free_months === null || fit.enough_frost_free_months === undefined) {
    checks.push({ ok: null, text: "We do not have enough frost data to check frost-free months." });
  } else {
    checks.push({
      ok: fit.enough_frost_free_months === 1,
      text: `${months(fit.frost_free_months)} a year are frost free. It needs about ${months(fit.months_to_mature)} to mature.`,
    });
  }

  const range = traits && traits.optimal_ph_min !== null && traits.optimal_ph_max !== null
    ? `${traits.optimal_ph_min} to ${traits.optimal_ph_max}` : null;
  if (fit.ph_gap === null || fit.ph_gap === undefined) {
    checks.push({ ok: null, text: "Soil acidity could not be compared, because the soil pH or the crop's pH range is missing." });
  } else if (Number(fit.ph_gap) === 0) {
    checks.push({ ok: true, text: `The soil pH (${soilPh}) is inside its ideal range of ${range}.` });
  } else {
    checks.push({ ok: false, text: `The soil pH (${soilPh}) is ${number(fit.ph_gap, 1)} outside its ideal range of ${range}.` });
  }
  return checks;
}

/** Turns the raw source text of a trait or pair into a plain status plus the readable detail. */
export function sourceNote(text) {
  const t = (text || "").trim();
  if (!t) return { checked: null, label: "Source not stated", detail: "" };
  const clean = (s) => s.replace(/\s*See DATA_PROVENANCE\.md\.?/gi, "").replace(/evidence_level/g, "evidence rating")
    .replace(/\s+in this pass/gi, "").replace(/\s{2,}/g, " ").trim();
  if (/^VERIFIED\b/i.test(t)) {
    return { checked: true, label: "Checked against a published source", detail: clean(t.replace(/^VERIFIED\s*[\u2014\u2013-]+\s*/i, "")) };
  }
  if (/not (independently |individually )?(source-)?verified/i.test(t)) {
    return { checked: false, label: "Not yet checked against a paper", detail: clean(t) };
  }
  return { checked: null, label: "Source", detail: clean(t) };
}

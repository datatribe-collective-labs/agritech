import { describe, expect, it } from "vitest";
import {
  cityHref, decode, evidenceLabel, fitChecks, frostLabel, humanize, mechanismLabel, number, plantHref, relativeFit,
  safeUrl, sourceNote,
} from "./format";
import type { FitChecks, PlantProfile } from "./types";

const traits = { frost_hardy: false, optimal_ph_min: 5.8, optimal_ph_max: 7 } as PlantProfile;
const fit = (over: Partial<FitChecks>): FitChecks => ({
  months_in_optimal_temp: null, frost_free_months: null, months_to_mature: null, enough_warm_months: null,
  enough_frost_free_months: null, ph_gap: null, trait_fit_share: null, ...over,
});

describe("links and wording", () => {
  it("builds links that survive spaces and decodes them back", () => {
    expect(plantHref("Des Moines", "Zea mays")).toBe("/city/Des%20Moines/plant/Zea%20mays");
    expect(decode("Zea%20mays")).toBe("Zea mays");
    expect(decode("100%")).toBe("100%");
    expect(cityHref("Lagos")).toBe("/city/Lagos");
  });

  it("keeps only web links", () => {
    expect(safeUrl("https://pmc.ncbi.nlm.nih.gov/x")).toBe("https://pmc.ncbi.nlm.nih.gov/x");
    expect(safeUrl("javascript:alert(1)")).toBeNull();
    expect(safeUrl(null)).toBeNull();
  });

  it("turns codes into plain words and keeps unknown codes readable", () => {
    expect(mechanismLabel("nitrogen_fixation")).toBe("Feeds the soil with nitrogen");
    expect(mechanismLabel("new_thing")).toBe("New thing");
    expect(evidenceLabel("scientific")).toBe("Backed by research");
    expect(frostLabel("frost_free")).toBe("No frost");
    expect(humanize("very_wet")).toBe("Very wet");
    expect(number(1559.2)).toBe("1,559");
    expect(number(null)).toBeNull();
  });

  it("keeps the fit bar between 0 and 1, relative to the best crop", () => {
    expect(relativeFit(0.2, 0.4)).toBe(0.5);
    expect(relativeFit(0.5, 0.4)).toBe(1);
    expect(relativeFit(0.2, 0)).toBe(0);
  });
});

describe("fit checks", () => {
  it("says what passed", () => {
    const checks = fitChecks(fit({ enough_warm_months: 1, months_in_optimal_temp: 9, months_to_mature: 2,
      enough_frost_free_months: 1, frost_free_months: 12, ph_gap: 0 }), traits, 5.9);
    expect(checks.map((c) => c.ok)).toEqual([true, true, true]);
    expect(checks[2].text).toContain("inside its ideal range of 5.8 to 7");
  });

  it("says what failed and what could not be checked", () => {
    const mixed = fitChecks(fit({ enough_warm_months: 0, months_in_optimal_temp: 1, months_to_mature: 1, ph_gap: 1.25 }), traits, 4.5);
    expect(mixed.map((c) => c.ok)).toEqual([false, null, false]);
    expect(mixed[0].text).toContain("1 month a year");
    expect(mixed[2].text).toContain("1.3 outside");
  });

  it("treats a frost hardy crop as passing the frost check", () => {
    const hardy = fitChecks(fit({}), { ...traits, frost_hardy: true, optimal_ph_min: null, optimal_ph_max: null }, 6);
    expect(hardy.map((c) => c.ok)).toEqual([null, true, null]);
  });
});

describe("source notes", () => {
  it("shows a checked source without the VERIFIED tag", () => {
    const note = sourceNote("VERIFIED — Zhang et al. (2014), Annals of Botany. Real study.");
    expect(note.checked).toBe(true);
    expect(note.detail).toBe("Zhang et al. (2014), Annals of Botany. Real study.");
  });

  it("says plainly when a source has not been checked, with no internal file names", () => {
    const note = sourceNote("Not independently verified in this pass — evidence_level as assigned by estimate. See DATA_PROVENANCE.md.");
    expect(note.checked).toBe(false);
    expect(note.label).toBe("Not yet checked against a paper");
    expect(note.detail).not.toMatch(/DATA_PROVENANCE|evidence_level|in this pass/);
  });

  it("keeps a partial citation inside an unchecked general reference", () => {
    const note = sourceNote("General agronomic reference — not individually source-verified in this pass. See DATA_PROVENANCE.md. Root depth: FAO-56.");
    expect(note.checked).toBe(false);
    expect(note.detail).toContain("Root depth: FAO-56");
  });

  it("handles empty and plain sources", () => {
    expect(sourceNote("").label).toBe("Source not stated");
    expect(sourceNote("FAO-56 Table 22").checked).toBeNull();
  });
});

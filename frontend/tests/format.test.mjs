import test from "node:test";
import assert from "node:assert/strict";
import { sourceNote, html, esc, safeUrl, mechanismLabel, evidenceLabel, relativeFit, fitChecks, frostLabel, number } from "../js/format.js";

test("html escapes inserted text but keeps nested html", () => {
  const evil = '<img src=x onerror="alert(1)">';
  assert.equal(html`<p>${evil}</p>`.text, "<p>&lt;img src=x onerror=&quot;alert(1)&quot;&gt;</p>");
  const inner = html`<b>${"a&b"}</b>`;
  assert.equal(html`<p>${inner}</p>`.text, "<p><b>a&amp;b</b></p>");
  assert.equal(html`${[html`<i>1</i>`, "<"]}`.text, "<i>1</i>&lt;");
  assert.equal(html`${null}${false}${undefined}`.text, "");
});

test("only web links are kept", () => {
  assert.equal(safeUrl("https://pmc.ncbi.nlm.nih.gov/x"), "https://pmc.ncbi.nlm.nih.gov/x");
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl(""), null);
  assert.equal(esc(`"'<`), "&quot;&#39;&lt;");
});

test("codes become plain wording, unknown codes stay readable", () => {
  assert.equal(mechanismLabel("nitrogen_fixation"), "Feeds the soil with nitrogen");
  assert.equal(mechanismLabel("new_thing"), "New thing");
  assert.equal(evidenceLabel("scientific"), "Backed by research");
  assert.equal(frostLabel("frost_free"), "No frost");
  assert.equal(number(1559.2), "1,559");
  assert.equal(number(null), null);
});

test("fit bar is relative to the best crop and stays between 0 and 1", () => {
  assert.equal(relativeFit(0.2, 0.4), 0.5);
  assert.equal(relativeFit(0.5, 0.4), 1);
  assert.equal(relativeFit(0.2, 0), 0);
});

test("fit checks say what passed, what failed and what could not be checked", () => {
  const traits = { frost_hardy: false, optimal_ph_min: 5.8, optimal_ph_max: 7 };
  const good = fitChecks({ enough_warm_months: 1, months_in_optimal_temp: 9, months_to_mature: 2,
    enough_frost_free_months: 1, frost_free_months: 12, ph_gap: 0 }, traits, 5.9);
  assert.deepEqual(good.map((c) => c.ok), [true, true, true]);
  assert.match(good[2].text, /inside its ideal range of 5.8 to 7/);

  const mixed = fitChecks({ enough_warm_months: 0, months_in_optimal_temp: 1, months_to_mature: 1,
    enough_frost_free_months: null, frost_free_months: null, ph_gap: 1.25 }, traits, 4.5);
  assert.deepEqual(mixed.map((c) => c.ok), [false, null, false]);
  assert.match(mixed[0].text, /1 month a year/);
  assert.match(mixed[2].text, /1\.3 outside/);

  const hardy = fitChecks({ enough_warm_months: null, enough_frost_free_months: null, ph_gap: null },
    { frost_hardy: true, optimal_ph_min: null, optimal_ph_max: null }, 6);
  assert.deepEqual(hardy.map((c) => c.ok), [null, true, null]);
});

test("source notes become plain statuses without internal file names", () => {
  const checked = sourceNote("VERIFIED \u2014 Zhang et al. (2014), Annals of Botany. Real study.");
  assert.equal(checked.checked, true);
  assert.equal(checked.detail, "Zhang et al. (2014), Annals of Botany. Real study.");

  const open = sourceNote("Not independently verified in this pass \u2014 evidence_level as originally assigned by estimate. See DATA_PROVENANCE.md.");
  assert.equal(open.checked, false);
  assert.equal(open.label, "Not yet checked against a paper");
  assert.ok(!/DATA_PROVENANCE|evidence_level|in this pass/.test(open.detail));

  const traits = sourceNote("General agronomic reference \u2014 not individually source-verified in this pass. See DATA_PROVENANCE.md. Root depth: FAO-56.");
  assert.equal(traits.checked, false);
  assert.match(traits.detail, /Root depth: FAO-56/);

  assert.equal(sourceNote("").label, "Source not stated");
  assert.equal(sourceNote("FAO-56 Table 22").checked, null);
});

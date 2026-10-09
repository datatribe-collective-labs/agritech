// The screens. Each view fetches what it needs and returns { title, crumbs, body, after }.

import * as api from "./api.js";
import {
  html, safeUrl, humanize, countryName, frostLabel, mechanismLabel, evidenceLabel,
  groupLabel, number, relativeFit, fitChecks, sourceNote, MONTHS,
} from "./format.js";

const link = {
  home: () => "#/",
  about: () => "#/about",
  city: (name) => `#/city/${encodeURIComponent(name)}`,
  plant: (name, species) => `#/city/${encodeURIComponent(name)}/plant/${encodeURIComponent(species)}`,
};

const LAST_CITY = "planting.lastCity";
const remember = (name) => { try { localStorage.setItem(LAST_CITY, name); } catch { /* storage blocked */ } };
const lastCity = () => { try { return localStorage.getItem(LAST_CITY); } catch { return null; } };

const STEMS = [[70, 92, .5], [180, 64, .2], [290, 104, .65], [400, 70, .35], [510, 98, .1], [620, 60, .45], [730, 92, .25],
  [840, 66, .55], [950, 100, .15], [1060, 62, .4], [1170, 96, .6], [1280, 68, .3], [1390, 102, .05], [1500, 74, .5]];

const sprouts = html`
<svg class="field" viewBox="0 0 1600 240" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
  <g class="stems">
    ${STEMS.map(([x, top, delay]) => html`
      <g style="--d:${delay}s">
        <path class="stem" pathLength="1" d="M${x} 168 C${x} ${168 - (168 - top) * 0.45}, ${x + 6} ${top + 30}, ${x + 3} ${top}"/>
        <path class="leaf" d="M${x + 3} ${top} q 26 -20 46 -4 q -20 22 -46 4z"/>
        <path class="leaf leaf-b" d="M${x + 3} ${top + 26} q -26 -18 -44 -2 q 20 20 44 2z"/>
      </g>`)}
  </g>
  <path class="soil soil-1" d="M0 168 C240 160 520 176 800 168 S1360 160 1600 170 V240 H0Z"/>
  <path class="soil soil-2" d="M0 190 C280 182 600 198 880 190 S1400 184 1600 192 V240 H0Z"/>
  <path class="soil soil-3" d="M0 214 C320 208 640 220 920 214 S1440 210 1600 216 V240 H0Z"/>
</svg>`;

function problem(error, retry) {
  const offline = error.status === 0;
  const text = offline
    ? "We could not reach the server. Check your connection and try again."
    : error.status === 404 ? "We could not find that page."
      : error.status === 503 ? "The data is being updated. Try again in a few minutes."
        : "Something went wrong on our side. Try again in a moment.";
  return html`
    <section class="notice" role="alert">
      <h1>${error.status === 404 ? "Not found" : "Could not load this page"}</h1>
      <p>${text}</p>
      <div class="actions">
        ${error.status === 404 ? "" : html`<button class="button" type="button" data-retry>Try again</button>`}
        <a class="button ghost" href="${link.home()}">Choose a city</a>
      </div>
    </section>`;
}
export { problem };

// ---------- Screen 1: choose a city ----------

export async function citiesView() {
  const cities = await api.cities();
  const saved = lastCity();
  const again = cities.find((c) => c.city === saved);

  const card = (c) => html`
    <a class="city-card ${c.has_recommendations ? "" : "is-quiet"}" href="${link.city(c.city)}" data-name="${(c.city + " " + countryName(c.country)).toLowerCase()}">
      <span class="city-name">${c.city}</span>
      <span class="city-country">${countryName(c.country)}</span>
      <span class="city-meta">${frostLabel(c.frost_zone)}${c.has_recommendations ? "" : " · no crop advice yet"}</span>
    </a>`;

  return {
    title: "Choose your city",
    crumbs: [{ label: "Cities" }],
    body: html`
      <section class="hero">
        ${sprouts}
        <div class="hero-text">
          <h1>What will grow well where you live?</h1>
          <p class="lede">Choose your city. You will see the crops that suit its soil and climate, and which ones grow well side by side.</p>
          <label class="search">
            <span class="sr-only">Search for your city</span>
            <input id="city-search" type="search" placeholder="Search for your city" autocomplete="off" enterkeyhint="go">
          </label>
          ${again ? html`<p class="again">Last time: <a href="${link.city(again.city)}">${again.city}</a></p>` : ""}
        </div>
      </section>
      <section aria-label="Cities">
        <div class="city-grid" id="city-grid">${cities.map(card)}</div>
        <p class="empty" id="city-none" hidden>No city matches that search. Check the spelling, or clear the search to see all ${cities.length} cities.</p>
      </section>`,
    after(root) {
      const input = root.querySelector("#city-search");
      const cards = [...root.querySelectorAll(".city-card")];
      const none = root.querySelector("#city-none");
      const apply = () => {
        const q = input.value.trim().toLowerCase();
        let shown = 0;
        cards.forEach((c) => { const hit = !q || c.dataset.name.includes(q); c.hidden = !hit; shown += hit ? 1 : 0; });
        none.hidden = shown > 0;
      };
      input.addEventListener("input", apply);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { const first = cards.find((c) => !c.hidden); if (first) first.click(); }
      });
    },
  };
}

// ---------- Screen 2: crops for one city ----------

function statTile(kind, label, value, note) {
  return html`
    <div class="stat stat-${kind}">
      <dt>${label}</dt>
      <dd class="${value === null ? "unknown" : ""}">${value ?? "Not measured"}</dd>
      ${note ? html`<dd class="note">${note}</dd>` : ""}
    </div>`;
}

function yearStrip(months) {
  const temps = months.map((m) => m.avg_temp_c).filter((t) => t !== null);
  if (!temps.length) return "";
  const low = Math.min(...temps), high = Math.max(...temps), span = Math.max(high - low, 1);
  const good = months.filter((m) => m.is_good_planting_month).length;
  return html`
    <section class="panel" aria-labelledby="year-title">
      <h2 id="year-title">The year here</h2>
      <p class="muted">${good ? `${good} month${good === 1 ? " is" : "s are"} good for planting (highlighted).` : "No month meets the planting rule below."}
        A good planting month is 15 to 35 °C, with no frost and at least 20 mm of rain. Averages over ten years.</p>
      <ol class="year" role="list">
        ${months.map((m) => html`
          <li class="${m.is_good_planting_month ? "good" : ""}">
            <span class="bar-wrap"><span class="bar" style="--h:${m.avg_temp_c === null ? 8 : 22 + ((m.avg_temp_c - low) / span) * 78}%"></span></span>
            <span class="t">${m.avg_temp_c === null ? "–" : `${Math.round(m.avg_temp_c)}°`}</span>
            <span class="rain" title="Average rain">${m.avg_monthly_rain_mm === null ? "–" : `${Math.round(m.avg_monthly_rain_mm)}`}</span>
            <span class="m">${MONTHS[m.month - 1]}</span>
          </li>`)}
      </ol>
      <p class="legend"><span class="dot t"></span>Temperature (°C) <span class="dot r"></span>Rain (mm a month)</p>
    </section>`;
}

export async function cityView({ city: name }) {
  const [detail, ranked, months] = await Promise.all([api.city(name), api.cityPlants(name), api.cityMonths(name)]);
  remember(detail.city);
  const plants = ranked.plants;
  const best = plants.length ? plants[0].suitability_score : 0;
  const groups = [...new Set(plants.map((p) => p.functional_group).filter(Boolean))].sort();

  const SHOWN_FIRST = 12;
  const plantCard = (p, i) => html`
    <a class="plant-card" href="${link.plant(detail.city, p.species)}" data-group="${p.functional_group || ""}" data-extra="${i >= SHOWN_FIRST ? "1" : ""}">
      <span class="rank" aria-label="Rank ${p.rank_in_city}">${p.rank_in_city}</span>
      <span class="plant-main">
        <span class="plant-name">${p.common_name || p.species}</span>
        <span class="latin">${p.species}</span>
        <span class="tags">
          ${p.functional_group ? html`<span class="tag">${groupLabel(p.functional_group)}</span>` : ""}
          <span class="tag ${p.observed_nearby ? "tag-yes" : "tag-no"}">${p.observed_nearby ? "Recorded nearby" : "Not recorded nearby"}</span>
        </span>
      </span>
      <span class="fit" role="img" aria-label="Match compared with the best crop here: ${Math.round(relativeFit(p.suitability_score, best) * 100)} percent">
        <span class="fit-bar"><i style="--w:${(relativeFit(p.suitability_score, best) * 100).toFixed(0)}%"></i></span>
        <span class="fit-label">${p.rank_in_city === 1 ? "Best match here" : `${Math.round(relativeFit(p.suitability_score, best) * 100)}% of the best`}</span>
      </span>
    </a>`;

  const goodMonths = months.filter((m) => m.is_good_planting_month).length;
  const stats = html`
    <dl class="stats">
      ${statTile("soil", "Soil acidity (pH)", number(detail.soil_ph, 1), detail.ph_band ? humanize(detail.ph_band) : null)}
      ${statTile("soil", "Soil type", detail.soil_texture_class ? humanize(detail.soil_texture_class) : null,
        detail.clay_pct !== null ? `${number(detail.clay_pct, 0)}% clay` : null)}
      ${statTile("rain", "Rain a year", detail.avg_annual_precip_mm !== null ? `${number(detail.avg_annual_precip_mm)} mm` : null,
        detail.rainfall_band ? humanize(detail.rainfall_band) : null)}
      ${statTile("frost", "Frost", frostLabel(detail.frost_zone),
        detail.avg_frost_days_per_year !== null ? `${number(detail.avg_frost_days_per_year, 0)} frost days a year` : null)}
      ${statTile("heat", "Good planting months", months.length ? `${goodMonths} of 12` : null, null)}
    </dl>`;

  const advice = ranked.recommendations_available
    ? html`
      <section class="panel" aria-labelledby="crops-title">
        <h2 id="crops-title">Crops for ${detail.city}</h2>
        <p class="muted">Ranked by how closely each crop matches the crops people have recorded near ${detail.city}. This is a guide, not a yield forecast.
          The bar compares each crop with the best match here. <a href="${link.about()}">How to read this</a></p>
        <div class="chips" role="group" aria-label="Filter by type of crop">
          <button type="button" class="chip is-on" data-filter="">All</button>
          ${groups.map((g) => html`<button type="button" class="chip" data-filter="${g}">${groupLabel(g)}</button>`)}
        </div>
        <div class="plant-list" id="plant-list">${plants.map(plantCard)}</div>
        ${plants.length > SHOWN_FIRST ? html`<p class="more"><button class="button ghost" type="button" data-more>Show all ${plants.length} crops</button></p>` : ""}
      </section>`
    : html`
      <section class="notice" role="status">
        <h2>No crop advice for ${detail.city} yet</h2>
        <p>${ranked.message}</p>
        <div class="actions"><a class="button" href="${link.home()}">Choose another city</a></div>
      </section>`;

  return {
    title: detail.city,
    crumbs: [{ label: "Cities", href: link.home() }, { label: detail.city }],
    body: html`
      <a class="back" href="${link.home()}">Back to cities</a>
      <header class="page-head">
        <h1 tabindex="-1">${detail.city}</h1>
        <p class="sub">${countryName(detail.country)}</p>
      </header>
      ${stats}
      ${advice}
      ${yearStrip(months)}`,
    after(root) {
      const chips = [...root.querySelectorAll(".chip")];
      const cards = [...root.querySelectorAll(".plant-card")];
      const more = root.querySelector("[data-more]");
      let group = "", expanded = false;
      const apply = () => {
        cards.forEach((card) => {
          const inGroup = group === "" || card.dataset.group === group;
          card.hidden = !(inGroup && (group !== "" || expanded || card.dataset.extra !== "1"));
        });
        if (more) more.parentElement.hidden = group !== "" || expanded;
      };
      chips.forEach((chip) => chip.addEventListener("click", () => {
        group = chip.dataset.filter;
        chips.forEach((c) => c.classList.toggle("is-on", c === chip));
        apply();
      }));
      if (more) more.addEventListener("click", () => { expanded = true; apply(); });
      apply();
    },
  };
}

// ---------- Screen 3: companions for one crop ----------

function sourceLine(text, url) {
  const note = sourceNote(text);
  return html`
    <p class="source">
      <span class="src-status ${note.checked === true ? "is-checked" : note.checked === false ? "is-open" : ""}">${note.label}</span>
      ${note.detail}${url ? html` <a href="${url}" target="_blank" rel="noopener noreferrer">Read the source</a>` : ""}
    </p>`;
}

function companionCard(c, own, cityName) {
  const url = safeUrl(c.source_url);
  const name = c.partner_common_name || c.partner;
  const open = c.partner_rank_in_city !== null && c.partner_rank_in_city !== undefined;
  return html`
    <article class="pair">
      <header class="pair-head">
        <span class="pair-names"><b>${own}</b><span class="plus" aria-hidden="true">+</span><b>${name}</b></span>
        <span class="badges">
          <span class="tag tag-yes">${c.relationship === "neutral" ? "Compatible" : "Helps each other"}</span>
          <span class="tag">${evidenceLabel(c.evidence_level)}</span>
        </span>
      </header>
      <h3>${mechanismLabel(c.mechanism)}</h3>
      <p class="why">${c.notes || "No explanation has been written for this pair yet."}</p>
      ${sourceLine(c.evidence_source, url)}
      ${open
        ? html`<a class="button ghost small" href="${link.plant(cityName, c.partner)}">See ${name} in ${cityName}</a>`
        : html`<p class="muted small">${name} has no ranking in ${cityName}.</p>`}
    </article>`;
}

export async function plantView({ city: cityName, species }) {
  const [detail, plant, pairs] = await Promise.all([api.city(cityName), api.plantInCity(cityName, species), api.companions(cityName, species)]);
  remember(detail.city);
  const own = plant.common_name || plant.species;
  const t = plant.traits;
  const checks = fitChecks(plant.fit, t, detail.soil_ph);
  const range = (a, b, unit = "") => (a === null || b === null ? null : `${a} to ${b}${unit}`);
  const needs = [
    ["Soil pH", range(t.optimal_ph_min, t.optimal_ph_max)],
    ["Temperature", range(t.optimal_temp_min_c, t.optimal_temp_max_c, " °C")],
    ["Time to mature", range(t.days_to_maturity_min, t.days_to_maturity_max, " days")],
    ["Water need", t.water_demand ? humanize(t.water_demand) : null],
    ["Drought tolerance", t.drought_tolerance ? humanize(t.drought_tolerance) : null],
    ["Frost", t.frost_hardy === null ? null : t.frost_hardy ? "Frost hardy" : "Not frost hardy"],
    ["Role for the soil", t.nitrogen_role ? humanize(t.nitrogen_role) : null],
  ];

  return {
    title: `${own} in ${detail.city}`,
    crumbs: [{ label: "Cities", href: link.home() }, { label: detail.city, href: link.city(detail.city) }, { label: own }],
    body: html`
      <a class="back" href="${link.city(detail.city)}">Back to crops for ${detail.city}</a>
      <header class="page-head">
        <h1 tabindex="-1">${own}</h1>
        <p class="sub"><span class="latin">${plant.species}</span>${plant.functional_group ? ` · ${groupLabel(plant.functional_group)}` : ""}</p>
        <p class="tags"><span class="tag">Rank ${plant.rank_in_city} in ${detail.city}</span>
          <span class="tag ${plant.observed_nearby ? "tag-yes" : "tag-no"}">${plant.observed_nearby ? "Recorded nearby" : "Not recorded nearby"}</span></p>
      </header>

      <section class="panel" aria-labelledby="pairs-title">
        <h2 id="pairs-title">Grows well with</h2>
        ${pairs.length
          ? html`<p class="muted">Crops that help ${own} when planted close by, and why. Only crops recorded near ${detail.city} are listed.</p>
                 <div class="pairs">${pairs.map((c) => companionCard(c, own, detail.city))}</div>`
          : html`<p class="empty-inline">No companion crop is listed for ${own} near ${detail.city}. Our companion list is written by hand and is still short, so this does not mean ${own} has no good partners.</p>`}
      </section>

      <section class="panel two" aria-labelledby="rank-title">
        <div>
          <h2 id="rank-title">How ${own} fits ${detail.city}</h2>
          <ul class="checks">
            ${checks.map((c) => html`<li class="${c.ok === true ? "yes" : c.ok === false ? "no" : "maybe"}"><span class="mark" aria-hidden="true"></span><span><span class="sr-only">${c.ok === true ? "Good: " : c.ok === false ? "Problem: " : "Unknown: "}</span>${c.text}</span></li>`)}
          </ul>
        </div>
        <div>
          <h2>What the model weighed</h2>
          ${plant.reasons.length
            ? html`<ol class="reasons">${plant.reasons.map((r) => html`<li>${r.text}</li>`)}</ol>`
            : html`<p class="muted">No single factor stood out for this crop.</p>`}
          <p class="muted small">These show how the model scored this crop. They are not proof of what makes it grow.</p>
        </div>
      </section>

      <section class="panel" aria-labelledby="needs-title">
        <h2 id="needs-title">What ${own} needs</h2>
        <dl class="needs">
          ${needs.map(([label, value]) => html`<div><dt>${label}</dt><dd class="${value === null ? "unknown" : ""}">${value ?? "Not known"}</dd></div>`)}
        </dl>
        ${t.notes ? html`<p class="muted">${t.notes}</p>` : ""}
        ${sourceLine(t.trait_source, safeUrl(t.source_url))}
      </section>`,
  };
}

// ---------- About ----------

export async function aboutView() {
  let info = null;
  try { info = await api.model(); } catch { /* the page still explains the data */ }
  const share = info && info.share_recorded !== null ? Math.round(info.share_recorded * 100) : null;
  return {
    title: "About the data",
    crumbs: [{ label: "Cities", href: link.home() }, { label: "About the data" }],
    body: html`
      <a class="back" href="${link.home()}">Back to cities</a>
      <header class="page-head"><h1 tabindex="-1">About the data</h1>
        <p class="sub">What the scores mean, and what they do not.</p></header>
      <section class="panel prose">
        <h2>What a score means</h2>
        <p>Each crop is compared with the crops people have recorded growing near the city. A crop that looks like those has a higher rank. It is a guide to what is likely to suit a place, not a promise of yield.</p>
        <h2>Where the information comes from</h2>
        <ul>
          <li>Crop records: GBIF, within 100 km of each city.</li>
          <li>Soil: the WoSIS soil database. Where a city has no measurement, we show it as not measured instead of guessing.</li>
          <li>Climate: ten-year averages from NASA.</li>
          <li>Companion crops and crop needs: a hand-written list. Every entry shows its source, including when it has not yet been checked against a paper.</li>
        </ul>
        ${info ? html`
          <h2>How well it works</h2>
          <p>${info.verdict}</p>
          <p class="muted">${info.rows} crop and city pairs across ${info.cities} cities were tested${share !== null ? `; ${share}% of them were recorded nearby` : ""}. Each city was scored by a model that had never seen it.</p>` : ""}
        <h2>Keep in mind</h2>
        <ul>${(info ? info.caveats : []).map((c) => html`<li>${c}</li>`)}</ul>
      </section>`,
  };
}

export function notFoundView() {
  return { title: "Not found", crumbs: [{ label: "Cities", href: link.home() }], body: problem({ status: 404 }) };
}

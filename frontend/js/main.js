// Routing, the breadcrumb bar and page changes.

import { html } from "./format.js";
import { aboutView, citiesView, cityView, notFoundView, plantView, problem } from "./views.js";

const main = document.getElementById("main");
const crumbsBar = document.getElementById("crumbs");
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let visit = 0;

function match() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch { return p; } });
  if (parts.length === 0) return [citiesView, {}];
  if (parts[0] === "about" && parts.length === 1) return [aboutView, {}];
  if (parts[0] === "city" && parts.length === 2) return [cityView, { city: parts[1] }];
  if (parts[0] === "city" && parts[2] === "plant" && parts.length === 4) return [plantView, { city: parts[1], species: parts[3] }];
  return [notFoundView, {}];
}

function drawCrumbs(items) {
  crumbsBar.innerHTML = html`<ol>${items.map((c, i) => c.href && i < items.length - 1
    ? html`<li><a href="${c.href}">${c.label}</a></li>`
    : html`<li><span aria-current="page">${c.label}</span></li>`)}</ol>`.text;
  const current = crumbsBar.querySelector("[aria-current]");
  if (current) current.scrollIntoView({ inline: "end", block: "nearest" });
}

function show(view) {
  const apply = () => {
    main.innerHTML = view.body.text;
    main.setAttribute("aria-busy", "false");
    drawCrumbs(view.crumbs || []);
    document.title = `${view.title} · Planting Intelligence`;
    window.scrollTo(0, 0);
    if (view.after) view.after(main);
    const heading = main.querySelector("h1");
    if (heading) heading.focus({ preventScroll: true });
    const retry = main.querySelector("[data-retry]");
    if (retry) retry.addEventListener("click", route);
  };
  if (document.startViewTransition && !reduced) document.startViewTransition(apply);
  else apply();
}

async function route() {
  const mine = ++visit;
  const [view, params] = match();
  main.setAttribute("aria-busy", "true");
  main.classList.add("loading");
  try {
    const result = await view(params);
    if (mine === visit) show(result);
  } catch (error) {
    if (mine === visit) show({ title: "Could not load", crumbs: [{ label: "Cities", href: "#/" }], body: problem(error) });
  } finally {
    if (mine === visit) main.classList.remove("loading");
  }
}

window.addEventListener("hashchange", route);
route();

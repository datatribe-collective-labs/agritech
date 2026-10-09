// Talks to the Planting Intelligence API. Answers are kept for the visit so going back is instant.

const base = ((window.PLANTING_CONFIG || {}).apiBase || "").replace(/\/$/, "");
const kept = new Map();
const seg = encodeURIComponent;

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function get(path) {
  if (kept.has(path)) return kept.get(path);
  let response;
  try { response = await fetch(base + path); }
  catch { throw new ApiError(0, "network"); }
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail; } catch { /* no body */ }
    throw new ApiError(response.status, detail || "request failed");
  }
  const data = await response.json();
  kept.set(path, data);
  return data;
}

export const cities = () => get("/cities");
export const city = (name) => get(`/cities/${seg(name)}`);
export const cityPlants = (name) => get(`/cities/${seg(name)}/plants?limit=100`);
export const cityMonths = (name) => get(`/cities/${seg(name)}/climate/monthly`);
export const plantInCity = (name, species) => get(`/cities/${seg(name)}/plants/${seg(species)}`);
export const companions = (name, species) => get(`/cities/${seg(name)}/plants/${seg(species)}/companions`);
export const model = () => get("/model");

// Server-side calls to the Planting Intelligence API. The browser never talks to the API directly.

import type { CityDetail, CityPlantDetail, CityPlants, CitySummary, ModelInfo, MonthlyClimate, PlantCompanion } from "./types";

const BASE = (process.env.API_URL ?? "https://94-237-15-238.sslip.io").replace(/\/$/, "");
const REFRESH_SECONDS = 300; // new model runs show up within five minutes

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE + path, { next: { revalidate: REFRESH_SECONDS } });
  } catch {
    throw new ApiError(0, "The API could not be reached");
  }
  if (!response.ok) throw new ApiError(response.status, `The API answered ${response.status}`);
  return (await response.json()) as T;
}

const seg = encodeURIComponent;

export const getCities = () => get<CitySummary[]>("/cities");
export const getCity = (city: string) => get<CityDetail>(`/cities/${seg(city)}`);
export const getCityPlants = (city: string) => get<CityPlants>(`/cities/${seg(city)}/plants?limit=100`);
export const getCityMonths = (city: string) => get<MonthlyClimate[]>(`/cities/${seg(city)}/climate/monthly`);
export const getPlantInCity = (city: string, species: string) =>
  get<CityPlantDetail>(`/cities/${seg(city)}/plants/${seg(species)}`);
export const getCompanions = (city: string, species: string) =>
  get<PlantCompanion[]>(`/cities/${seg(city)}/plants/${seg(species)}/companions`);
export const getModelInfo = () => get<ModelInfo>("/model");

/** The HTTP status behind a failed call (0 when the API could not be reached). */
export const statusOf = (error: unknown) => (error instanceof ApiError ? error.status : 500);

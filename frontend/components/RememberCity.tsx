"use client";

import { useEffect } from "react";

/** Remembers the last city on this device so the home screen can offer it again. Renders nothing. */
export function RememberCity({ city }: { city: string }) {
  useEffect(() => {
    try { localStorage.setItem("planting.lastCity", city); } catch { /* storage blocked */ }
  }, [city]);
  return null;
}

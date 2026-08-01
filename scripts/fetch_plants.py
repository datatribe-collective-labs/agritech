"""
Select GBIF data fetch for agricultural plant species only.
"""

import os
import sys
import time
import logging
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db_utils import get_engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GBIF_API = "https://api.gbif.org/v1/occurrence/search"

# Selected plants species
AGRICULTURAL_SPECIES = [
    "Zea mays",
    "Phaseolus vulgaris",
    "Cucurbita pepo",
    "Triticum aestivum",
    "Trifolium repens",
    "Oryza sativa",
    "Solanum lycopersicum",
    "Ocimum basilicum",
    "Tagetes erecta",
    "Brassica oleracea",
    "Allium sativum",
    "Petroselinum crispum",
    "Daucus carota",
    "Allium cepa",
    "Allium porrum",
    "Apium graveolens",
    "Vicia faba",
    "Medicago sativa",
    "Sorghum bicolor",
    "Vigna unguiculata",
    "Coffea arabica",
    "Carica papaya",
    "Arachis hypogaea",
    "Manihot esculenta",
    "Cajanus cajan",
    "Saccharum officinarum",
    "Solanum tuberosum",
    "Tanacetum vulgare",
    "Helianthus annuus",
    "Cucurbita maxima",
    "Capsicum annuum",
    "Glycine max",
    "Hordeum vulgare",
    "Trifolium subterraneum",
    "Vicia sativa",
    "Sesbania bispinosa",
    "Azolla pinnata",
    "Foeniculum vulgare",
    "Lavandula angustifolia",
    "Rosa",
    "Musa",
]

# Fetch occurrences for a specific species
def fetch_species_occurrences(
    species: str,
    limit: int = 300,
    has_coordinate: bool = True,
    has_event_date: bool = True,
) -> list:
    """
    Fetches GBIF occurrences for a single species.
    Requires coordinates AND event dates for seasonal signal.
    """
    params = {
        "scientificName":  species,
        "hasCoordinate":   str(has_coordinate).lower(),
        "hasGeospatialIssue": "false",
        "status":          "ACCEPTED",
        "limit":           min(limit, 300),
        "offset":          0,
    }

    if has_event_date:
        params["month"] = ",".join(str(m) for m in range(1, 13))

    all_results = []
    page = 0

    while len(all_results) < limit:
        params["offset"] = page * 300
        try:
            response = requests.get(GBIF_API, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                break

            all_results.extend(results)

            if data.get("endOfRecords", True):
                break

            page += 1
            time.sleep(0.5)  # be polite to GBIF API

        except Exception as e:
            logger.warning(f"  GBIF error for {species}: {e}")
            break

    return all_results[:limit]

# Parse a GBIF occurrence record into the schema
def parse_occurrence(record: dict, ingested_at: datetime) -> dict:
    """Parses a GBIF occurrence record into our schema."""
    return {
        "species":              record.get("species") or record.get("scientificName"),
        "scientific_name":      record.get("scientificName"),
        "kingdom":              record.get("kingdom", "Plantae"),
        "phylum":               record.get("phylum"),
        "class":                record.get("class"),
        "order":                record.get("order"),
        "family":               record.get("family"),
        "genus":                record.get("genus"),
        "country":              record.get("countryCode"),
        "continent":            record.get("continent"),
        "state_province":       record.get("stateProvince"),
        "locality":             record.get("locality"),
        "latitude":             record.get("decimalLatitude"),
        "longitude":            record.get("decimalLongitude"),
        "elevation":            record.get("elevation"),
        "year":                 record.get("year"),
        "month":                record.get("month"),
        "day":                  record.get("day"),
        "event_date":           record.get("eventDate"),
        "habitat":              record.get("habitat"),
        "occurrence_status":    record.get("occurrenceStatus", "PRESENT"),
        "basis_of_record":      record.get("basisOfRecord"),
        "coordinate_uncertainty": record.get("coordinateUncertaintyInMeters"),
        "identified_by":        record.get("identifiedBy"),
        "recorded_by":          record.get("recordedBy"),
        "ingested_at":          ingested_at,
    }

# Save parsed records to the database
def save_to_postgres(records: list) -> int:
    """Saves parsed records to the plants raw table."""
    if not records:
        return 0

    df = pd.DataFrame(records)

    # Filter: must have coordinates
    df = df.dropna(subset=["latitude", "longitude"])

    # Filter: only Plantae
    df = df[df["kingdom"].str.upper() == "PLANTAE"]

    if df.empty:
        return 0

    engine = get_engine()
    df.to_sql(
        "plants",
        engine,
        schema="public",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    return len(df)

# Fetch all plant species
def fetch_plants(
    species_list: list = None,
    records_per_species: int = 300,
):
    """
    Main fetch function — fetches all agricultural species.
    """
    species_list = species_list or AGRICULTURAL_SPECIES
    ingested_at  = datetime.utcnow()
    total_saved  = 0

    logger.info("=" * 55)
    logger.info("  Agricultural Species GBIF Fetch")
    logger.info(f"  {len(species_list)} species × ~{records_per_species} records")
    logger.info("=" * 55)

    for i, species in enumerate(species_list, 1):
        logger.info(f"[{i:2d}/{len(species_list)}] Fetching: {species}")

        records = fetch_species_occurrences(
            species=species,
            limit=records_per_species,
            has_coordinate=True,
            has_event_date=True,
        )

        if not records:
            # Try without event date filter — some species have sparse dated records
            logger.info(f"  No dated records — trying without date filter")
            records = fetch_species_occurrences(
                species=species,
                limit=records_per_species,
                has_coordinate=True,
                has_event_date=False,
            )

        parsed = [parse_occurrence(r, ingested_at) for r in records]
        n_saved = save_to_postgres(parsed)
        total_saved += n_saved

        # Month distribution for this species
        months = [r.get("month") for r in records if r.get("month")]
        month_dist = {}
        for m in months:
            month_dist[m] = month_dist.get(m, 0) + 1

        logger.info(
            f"  → {len(records)} fetched, {n_saved} saved"
            + (f" | months: {dict(sorted(month_dist.items()))}" if month_dist else "")
        )

        time.sleep(1)  # 1 second between species — respectful rate limiting

    logger.info("\n" + "=" * 55)
    logger.info(f"  Total records saved: {total_saved}")
    logger.info("=" * 55)

    return total_saved


if __name__ == "__main__":
    fetch_plants()

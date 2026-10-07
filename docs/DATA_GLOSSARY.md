# Data glossary

Plain-language meaning of the main columns in the warehouse and the ML tables.

## Terms
| Term | Meaning |
|---|---|
| Growing degree days (GDD) | Heat units for crops. Each day adds (average temperature - 10 C), never below 0. A month or year of GDD tells you if a crop can finish its growth. |
| Evapotranspiration | Water that leaves soil and plants for the air each day. It is what crops need. |
| Water deficit (mm per day) | Evapotranspiration minus rain. Positive means irrigation is needed. Covers only the forecast window (about 7 days). |
| Frost zone | How many days a year fall to 0 C or below: `frost_free` (0), `light_frost` (under 30), `moderate_frost` (under 90), `heavy_frost` (under 150), `severe_frost` (150 or more). It ignores heat and rain. |
| Crop heat class | From yearly GDD: `cool_season_only` (under 1000), `mixed_season` (1000-2000), `tropical_viable` (over 2000). |
| Rainfall band | From yearly rain: `very_dry` (under 250 mm), `dry` (under 500), `moderate` (under 750), `wet` (under 1200), `very_wet`. |
| pH band | `strongly_acidic` (under 5.5), `moderately_acidic` (under 6.5), `neutral` (under 7.5), `alkaline` (under 8.5), `strongly_alkaline`. |
| Species near a city | A crop with at least one GBIF record within 500 km of the city centre (setting `species_radius_km` in `dbt_project.yml`). It shows where a crop was recorded, not how well it grows there. |
| Current conditions score | 100 minus penalties for today's frost (30), heat (20), severe/moderate water stress (20/10), low soil nitrogen (10) and flood risk (10). A snapshot of today. |
| Relationship score | Companion pair points (+3 beneficial, +1 neutral, -5 antagonistic) times evidence (x3 scientific, x2 traditional, x1 anecdotal). |
| Soil fertility points | 0-4: nitrogen at least 1.0 g/kg, organic carbon at least 10 g/kg, pH 6-7, loam/clay loam/silty texture. |

## Rules of thumb that still need expert validation
Soil texture classes, nitrogen cut-off (1.0 g/kg), water stress and irrigation urgency bands,
flood-risk rule (peak flow above 3x average), heat-stress limit (35 C is a rice figure),
crop heat class limits, "tropical crop viable" (18 C) and "cool-season viable" (8-20 C),
the good-planting-month rule, the points in the current conditions score.

## Data behaviour worth knowing
- Missing values stay empty. Nothing is filled with an assumed pH, temperature or rainfall.
- Monthly climate is the average of that calendar month over the years we hold (months with fewer than 25 days of data are skipped).
- ML labels (`top_species_1..3`) are counts of recorded observations, capped by how many GBIF records we fetched per species, and they reflect where people record plants.

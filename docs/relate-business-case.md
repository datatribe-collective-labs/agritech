# Relate — Business Case

**Relational Planting Intelligence** · DataTribe Collective × UpCloud

---

## Summary

Relate is a data-driven recommendation service that connects plant, soil, climate and location data to help growers decide what to plant, and what to plant alongside it.

A grower gives their location and the plants they are interested in. Relate returns suitable plant groups, with the reason behind each recommendation.

It is built on public data sources, orchestrated through an automated pipeline, and hosted on EU-sovereign infrastructure.

This document sets out the case for the MVP: what it does, who it serves, and why it is worth building.

---

## The problem

Intensive monoculture — the same crop on the same land, season after season — strips soil of the organic matter and biological diversity that keep it productive. Degraded soil produces less, needs more input, and leaves land vulnerable to drought and erosion. A majority of the world's land is projected to be degraded by 2050.

Companion and compatibility planting is one of the established responses. Growing species together that suit both the place and each other restores soil structure and fertility, spreads pest and disease risk, and produces more from the same ground.

The obstacle is not that this is unknown. It is that acting on it requires assembling information that sits in separate places — soil properties, climate history, the requirements of individual plants, and the documented relationships between species. Bringing all of that together for one specific location is the work, and most growers have no practical way to do it.

The result is that growers fall back on experience, local advice, or generic guidance that is not specific to their site.

---

## The solution

Relate turns dispersed public data into a specific answer for a specific place.

It answers two questions:

1. **Which plants suit this place?** — matching a plant's requirements against the soil, climate and conditions at a location
2. **Which plants go well together?** — the relationships between species growing alongside each other

### What the grower provides

- Location
- The plants they are interested in or already growing

### What the system does

- Derives soil and climate conditions from the location, so the grower does not need to know their own soil type or pH
- Identifies which plants are viable in those conditions
- Assesses which of those are compatible with the grower's chosen plants and with each other

### What the grower receives

Suitable plant groups, with the reason for each recommendation.

The reasoning is the product. A list of plant names is available anywhere. A list that explains why each species belongs — what it contributes, what it tolerates, what it protects against — is what makes a recommendation actionable and worth trusting.

---

## What it serves

The same capability answers several needs:

- **Soil preservation and regeneration** — breaking monoculture with species that restore fertility and structure
- **Crop planning** — choosing what suits a site before committing to it
- **Diversification** — adding species that spread risk and produce additional yield
- **Agroforestry** — combining trees and crops in layered systems
- **Food production** — choosing plants that will grow well and feed a household

Users are growers making planting decisions: smallholder farms, market gardens, urban food production, and the advisory organisations, cooperatives and extension services that support them.

---

## Value

For the grower:

- Better-matched planting, and therefore better yield from the same land
- Additional produce from added species
- Lower input costs where companion species contribute nutrients or suppress pests
- Reduced exposure to the concentration risk that monoculture creates
- Decisions made on evidence rather than guesswork

Against the cost of seedlings and the labour to plant them.

For advisory organisations, the same capability delivers site-specific guidance at a scale no individual advisor can hold in their head, with a consistent record of what was recommended and why.

---

## Revenue model

Free for small-scale growers. Commercial licensing for large-scale operators.

The free tier is deliberate. Smallholders are the largest group of users and the least able to pay, and reaching them is central to the project's purpose. Commercial operators, advisory organisations and supply-chain buyers derive direct commercial benefit from better planting decisions and are the paying side of the model.

---

## How it is built

The MVP is an end-to-end data pipeline delivering a recommendation through an interface:

- **Ingestion** — automated collection from public APIs, orchestrated by Apache Airflow
- **Storage** — containerised PostgreSQL
- **Transformation** — cleaning, quality checks and feature engineering into usable plant and place profiles
- **Recommendation** — matching plants to conditions, and assessing compatibility between species
- **Delivery** — served through an API to a user interface

Data sources are public and open: GBIF for plant occurrence, ISRIC SoilGrids for soil properties, NASA POWER for climate history, Open-Meteo for water balance, OpenWeatherMap for current conditions. Plant profile and compatibility data is curated from published agronomic sources, with each recommendation carrying its evidence.

Running costs are cloud infrastructure and ongoing data curation. Adding further crops or regions is a matter of extending the curated plant data — the platform itself does not change.

---

## Infrastructure

Relate runs on UpCloud, EU-sovereign cloud infrastructure.

This is a deliberate choice rather than a default. The service handles location data about real growers and real land, and EU data residency is a requirement for several of the public funding routes the project would pursue. Meeting it by design rather than retrofitting it later is materially simpler.

For UpCloud, Relate exercises the full stack as a genuine workload — ingestion, orchestration, storage, transformation, model serving, API and deployment — demonstrating that a lightweight, scalable data and AI service can be built and run end to end on EU infrastructure.

---

## Risks

**Recommendation quality.** A poor recommendation costs a grower a season. Every recommendation carries its reasoning and its source, confidence is stated rather than implied, and species with documented disease or phytosanitary concerns are excluded outright rather than scored down.

**Data coverage.** Plant trait and compatibility data is uneven across species and regions. Where information is missing, the system reports lower confidence rather than filling the gap with assumption.

**Regional transfer.** Evidence gathered in one climate or soil type does not automatically hold in another. Recommendations record where their supporting evidence came from.

**Delivery.** A part-time team and a fixed delivery window. Scope is held to a defined MVP: inputs, compatibility assessment, and explained output. Everything else is sequenced after it.

---

## Scope

**The MVP answers two questions and nothing else:** which plants suit this place, and which plants go well together.

Not part of it:

- **When** to sow, plant out or harvest
- **Where** to position plants across a site
- Crop rotation and succession planning
- Machine learning — the recommendation is built on curated evidence and stated rules, not learned from training data

These are deliberate exclusions, not omissions. Each is a question the same platform can answer later by extending what already exists, rather than by rebuilding it. Holding the MVP to two questions is what makes it deliverable and what makes each recommendation explainable.

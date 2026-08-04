# Notes about /data
Here we can store local small datasets to later integrate into the database.

**Script to pull living languages plant names from [wikidata](https://query.wikidata.org/)**
```
SELECT ?latinName ?lang ?commonName ?alias WHERE {
  # 1. Your batch of 42 binomial names
  VALUES ?latinName { 
    "Zea mays"
    "Phaseolus vulgaris"
    "Cucurbita pepo"
    "Triticum aestivum"
    "Trifolium repens"
    "Oryza sativa"
    "Solanum lycopersicum"
    "Ocimum basilicum"
    "Tagetes erecta"
    "Brassica oleracea"
    "Allium sativum"
    "Petroselinum crispum"
    "Daucus carota"
    "Allium cepa"
    "Allium porrum"
    "Apium graveolens"
    "Vicia faba"
    "Medicago sativa"
    "Sorghum bicolor"
    "Vigna unguiculata"
    "Coffea arabica"
    "Carica papaya"
    "Arachis hypogaea"
    "Manihot esculenta"
    "Cajanus cajan"
    "Saccharum officinarum"
    "Solanum tuberosum"
    "Tanacetum vulgare"
    "Helianthus annuus"
    "Cucurbita maxima"
    "Capsicum annuum"
    "Glycine max"
    "Hordeum vulgare"
    "Trifolium subterraneum"
    "Vicia sativa"
    "Sesbania bispinosa"
    "Azolla pinnata"
    "Foeniculum vulgare"
    "Lavandula angustifolia"
    "Rosa"
    "Musa"
  }
  
  # 2. Match species taxon name on Wikidata
  ?plant wdt:P225 ?latinName .
  
  # 3. Pull primary label and language tag
  ?plant rdfs:label ?commonName .
  BIND(LANG(?commonName) AS ?lang)
  
  # 4. Pull secondary/alternative vernacular aliases
  OPTIONAL {
    ?plant skos:altLabel ?alias .
    FILTER(LANG(?alias) = ?lang)
  }
}
ORDER BY ?latinName ?lang
```

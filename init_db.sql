-- This SQL file runs AUTOMATICALLY the very first time
-- the Postgres container starts (because we mount it into
-- /docker-entrypoint-initdb.d/).


-- PLANTS  (from GBIF occurrence API)
CREATE TABLE IF NOT EXISTS plants (
    id               SERIAL PRIMARY KEY,
    species          TEXT,
    scientific_name  TEXT,
    kingdom          TEXT,
    phylum           TEXT,
    class            TEXT,
    "order"          TEXT,         
    family           TEXT,
    genus            TEXT,
    country          TEXT,
    continent        TEXT,
    state_province   TEXT,
    locality         TEXT,
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION,
    elevation        DOUBLE PRECISION,
    year             INTEGER,
    month            INTEGER,
    day              INTEGER,
    event_date       TEXT,
    habitat          TEXT,
    occurrence_status TEXT,
    basis_of_record  TEXT,
    institution_code TEXT,
    dataset_name     TEXT,
    publisher        TEXT,
    coordinate_uncertainty DOUBLE PRECISION,
    identified_by    TEXT,
    recorded_by      TEXT,
    ingested_at      TIMESTAMP DEFAULT NOW()   
);


-- SOIL  (from ISRIC SoilGrids API)
CREATE TABLE IF NOT EXISTS soil (
    id              SERIAL PRIMARY KEY,
    city            TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    clay_0_5cm      DOUBLE PRECISION,   
    sand_0_5cm      DOUBLE PRECISION,
    silt_0_5cm      DOUBLE PRECISION,
    soc_0_5cm       DOUBLE PRECISION,   
    phh2o_0_5cm     DOUBLE PRECISION,   
    nitrogen_0_5cm  DOUBLE PRECISION, 
    ingested_at     TIMESTAMP DEFAULT NOW()
);


-- WEATHER  (from OpenWeatherMap API)
CREATE TABLE IF NOT EXISTS weather (
    id                  SERIAL PRIMARY KEY,
    city                TEXT,
    country             TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    temperature_c       DOUBLE PRECISION,
    feels_like_c        DOUBLE PRECISION,
    min_temp_c          DOUBLE PRECISION,
    max_temp_c          DOUBLE PRECISION,
    humidity_pct        DOUBLE PRECISION,
    pressure_hpa        DOUBLE PRECISION,
    ground_pressure_hpa DOUBLE PRECISION,
    wind_speed_mps      DOUBLE PRECISION,
    wind_direction_deg  DOUBLE PRECISION,
    cloud_cover_pct     DOUBLE PRECISION,
    weather_main        TEXT,
    description         TEXT,
    visibility_m        DOUBLE PRECISION,
    ingested_at         TIMESTAMP DEFAULT NOW()
);


-- WATER  (from Open-Meteo APIs)
CREATE TABLE IF NOT EXISTS water (
    id                       SERIAL PRIMARY KEY,
    city                     TEXT,
    latitude                 DOUBLE PRECISION,
    longitude                DOUBLE PRECISION,
    avg_daily_precip_mm      DOUBLE PRECISION,
    avg_daily_et0_mm         DOUBLE PRECISION,
    avg_daily_water_deficit_mm DOUBLE PRECISION,
    forecast_start_date      TEXT,
    forecast_end_date        TEXT,
    avg_river_discharge_m3s  DOUBLE PRECISION,
    max_river_discharge_m3s  DOUBLE PRECISION,
    ingested_at              TIMESTAMP DEFAULT NOW()
);

-- Let the airflow user know the tables are ready
SELECT 'planting_db tables created successfully' AS status;


-- NASA POWER  (historical daily climate, 10 years)
CREATE TABLE IF NOT EXISTS nasa_climate (
    id                  SERIAL PRIMARY KEY,
    city                TEXT,
    country             TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    date                DATE,
    t2m                 DOUBLE PRECISION,   -- avg temp
    t2m_max             DOUBLE PRECISION,   -- max temp
    t2m_min             DOUBLE PRECISION,   -- min temp
    prectotcorr         DOUBLE PRECISION,   -- precipitation mm/day
    rh2m                DOUBLE PRECISION,   -- relative humidity %
    ws2m                DOUBLE PRECISION,   -- wind speed m/s
    allsky_sfc_sw_dwn   DOUBLE PRECISION,   -- solar radiation
    gwetroot            DOUBLE PRECISION,   -- root zone soil wetness
    ingested_at         TIMESTAMP DEFAULT NOW()
);

-- Index on city+date for fast lookups
CREATE INDEX IF NOT EXISTS idx_nasa_city_date ON nasa_climate(city, date);

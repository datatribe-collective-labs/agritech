"""
API tests against a small in-memory database (SQLite) that mimics the mart tables.

Three cities: Lagos and Nairobi have scores; Harare has none (no crop recorded near it).
"""

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from api.main import create_app  # noqa: E402

SCHEMA = """
CREATE TABLE mart_ml_annual_features (city, country, latitude, longitude, frost_zone, soil_ph, clay_pct, sand_pct,
  silt_pct, organic_carbon_g_kg, nitrogen_g_kg, soil_texture_class, ph_band, rainfall_band, avg_annual_precip_mm,
  avg_frost_days_per_year, frost_free_days_per_year, avg_annual_gdd, temp_variability_c, water_stress_category,
  irrigation_needed_flag, soil_feature_completeness, climate_feature_completeness, last_updated_at);
CREATE TABLE mart_planting_features (city, month, month_name, avg_temp_c, avg_max_temp_c, avg_min_temp_c,
  avg_monthly_rain_mm, avg_monthly_gdd, avg_frost_days_in_month, is_frost_free_month, is_good_planting_month);
CREATE TABLE mart_species_city_suitability (city, species, common_name, functional_group, observation_count,
  months_in_optimal_temp, frost_free_months, months_to_mature, enough_warm_months, enough_frost_free_months,
  ph_gap, trait_fit_share);
CREATE TABLE mart_plant_profiles (species, common_name, family, functional_group, growth_habit, root_depth_class,
  nitrogen_role, nitrogen_fixation, drought_tolerance, shade_tolerance, water_demand, frost_hardy, optimal_ph_min,
  optimal_ph_max, optimal_temp_min_c, optimal_temp_max_c, days_to_maturity_min, days_to_maturity_max, notes,
  trait_source, source_url);
CREATE TABLE mart_city_companions (city, pair_rank, species_a, species_b, mechanism, benefit_category,
  evidence_level, relationship_score, relationship, notes, evidence_source, source_url);
CREATE TABLE ml_species_city_suitability (city, species, observed_nearby, suitability_score, rank_in_city);
CREATE TABLE ml_species_city_explanations (city, species, reason_rank, feature, feature_label, feature_value,
  effect, contribution, reason);
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as c:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                c.execute(text(statement))
        c.execute(text("""INSERT INTO mart_ml_annual_features (city, country, latitude, longitude, frost_zone,
            soil_ph, last_updated_at) VALUES
            ('Lagos','NG',6.5,3.4,'frost_free',5.9,'2026-10-01 06:00:00'),
            ('Nairobi','KE',-1.3,36.8,'frost_free',6.2,'2026-10-01 06:00:00'),
            ('Harare','ZW',-17.8,31.0,'frost_free',5.8,NULL),
            ('Hanoi','VN',21.0,105.8,'frost_free',NULL,NULL)"""))
        c.execute(text("""INSERT INTO mart_planting_features (city, month, month_name, avg_temp_c, is_frost_free_month,
            is_good_planting_month) VALUES ('Lagos',2,'Feb',28.1,1,1),('Lagos',1,'Jan',27.0,1,0)"""))
        c.execute(text("""INSERT INTO mart_plant_profiles (species, common_name, family, functional_group,
            frost_hardy, optimal_ph_min, optimal_ph_max, days_to_maturity_min, trait_source) VALUES
            ('Zea mays','Maize','Poaceae','cereal',0,5.8,7.0,60,'General reference'),
            ('Phaseolus vulgaris','Common Bean','Fabaceae','legume',0,6.0,7.5,50,'Dakora & Keya (1997)')"""))
        c.execute(text("""INSERT INTO mart_species_city_suitability (city, species, common_name, functional_group,
            observation_count, months_in_optimal_temp, frost_free_months, months_to_mature, enough_warm_months,
            enough_frost_free_months, ph_gap, trait_fit_share) VALUES
            ('Lagos','Zea mays','Maize','cereal',40,9,12,2,1,1,0,1.0),
            ('Lagos','Phaseolus vulgaris','Common Bean','legume',0,6,12,2,1,1,0.1,0.67),
            ('Nairobi','Zea mays','Maize','cereal',12,8,12,2,1,1,0,1.0)"""))
        c.execute(text("""INSERT INTO ml_species_city_suitability VALUES
            ('Lagos','Zea mays',1,0.81,1),('Lagos','Phaseolus vulgaris',0,0.35,2),('Nairobi','Zea mays',1,0.62,1)"""))
        c.execute(text("""INSERT INTO ml_species_city_explanations VALUES
            ('Lagos','Zea mays',1,'frost_free_months','Frost-free months',12,'raises',0.4,
             'Frost-free months: 12 raises its score compared with other crops in Lagos'),
            ('Lagos','Zea mays',2,'ph_gap','Soil pH distance outside the ideal range',0,'raises',0.2,
             'Soil pH distance outside the ideal range: 0 raises its score compared with others in Lagos')"""))
        c.execute(text("""INSERT INTO mart_city_companions VALUES
            ('Lagos',1,'Zea mays','Phaseolus vulgaris','nitrogen_fixation','nutrient_sharing',
             'scientific',9,'beneficial','Beans fix nitrogen that feeds maize',
             'VERIFIED - Zhang 2014','https://example.org/z')"""))

    report = tmp_path / "report.json"
    report.write_text(json.dumps({"verdict": "The model beats the best simple baseline.", "rows": 6, "cities": 2,
                                  "model": {"roc_auc": 0.7}, "gain_95_percent_range": [0.03, 0.14]}))
    monkeypatch.setenv("MODEL_REPORT_PATH", str(report))
    return TestClient(create_app(engine=engine, schema=""))


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_all_cities_flags_the_city_without_scores(client):
    cities = {c["city"]: c for c in client.get("/cities").json()}
    assert set(cities) == {"Hanoi", "Harare", "Lagos", "Nairobi"}
    assert cities["Lagos"]["has_recommendations"] is True
    assert cities["Harare"]["has_recommendations"] is False
    assert cities["Hanoi"]["soil_ph"] is None           # missing stays empty


def test_city_filters(client):
    assert [c["city"] for c in client.get("/cities?search=la").json()] == ["Lagos"]
    assert [c["city"] for c in client.get("/cities?country=ke").json()] == ["Nairobi"]
    unscored = client.get("/cities?has_recommendations=false").json()
    assert [c["city"] for c in unscored] == ["Hanoi", "Harare"]


def test_city_lookup_ignores_capitals_and_unknown_city_is_404(client):
    assert client.get("/cities/lagos").json()["city"] == "Lagos"
    assert client.get("/cities/Atlantis").status_code == 404


def test_plants_for_a_city_are_ranked_with_reasons(client):
    body = client.get("/cities/Lagos/plants").json()
    assert body["recommendations_available"] is True
    assert [p["species"] for p in body["plants"]] == ["Zea mays", "Phaseolus vulgaris"]
    maize = body["plants"][0]
    assert maize["suitability_score"] == 0.81 and maize["rank_in_city"] == 1
    assert [r["rank"] for r in maize["reasons"]] == [1, 2]
    assert maize["reasons"][0]["text"].startswith("Frost-free months: 12 raises")
    assert body["plants"][1]["reasons"] == []


def test_plants_limit_and_filters(client):
    assert len(client.get("/cities/Lagos/plants?limit=1").json()["plants"]) == 1
    legumes = client.get("/cities/Lagos/plants?functional_group=legume").json()["plants"]
    assert [p["species"] for p in legumes] == ["Phaseolus vulgaris"]
    assert client.get("/cities/Lagos/plants?min_score=0.5").json()["plants"][0]["species"] == "Zea mays"
    assert client.get("/cities/Lagos/plants?limit=0").status_code == 422


def test_city_without_scores_says_so_instead_of_inventing_any(client):
    body = client.get("/cities/Harare/plants").json()
    assert body["recommendations_available"] is False
    assert body["plants"] == []
    assert "No crop has been recorded" in body["message"]


def test_city_without_soil_ph_gets_its_own_reason(client):
    body = client.get("/cities/Hanoi/plants").json()
    assert body["recommendations_available"] is False
    assert "no soil pH measurement" in body["message"]
    assert "no soil pH measurement" in client.get("/cities/Hanoi/context").json()["caveats"][0]


def test_one_plant_in_one_city_has_fit_checks_and_crop_needs(client):
    body = client.get("/cities/Lagos/plants/zea mays").json()
    assert body["fit"]["months_in_optimal_temp"] == 9
    assert body["traits"]["optimal_ph_min"] == 5.8
    assert body["traits"]["trait_source"] == "General reference"
    assert client.get("/cities/Nairobi/plants/Phaseolus vulgaris").status_code == 404


def test_monthly_climate_is_in_calendar_order(client):
    months = client.get("/cities/Lagos/climate/monthly").json()
    assert [m["month"] for m in months] == [1, 2]
    assert months[1]["is_good_planting_month"] is True
    assert months[0]["avg_max_temp_c"] is None


def test_companions(client):
    pairs = client.get("/cities/Lagos/companions").json()
    assert pairs[0]["species_b"] == "Phaseolus vulgaris" and pairs[0]["relationship_score"] == 9
    assert client.get("/cities/Nairobi/companions").json() == []


def test_companions_of_a_plant_work_from_either_side_of_the_pair(client):
    maize = client.get("/cities/Lagos/plants/Zea mays/companions").json()
    bean = client.get("/cities/lagos/plants/phaseolus vulgaris/companions").json()
    assert [c["partner"] for c in maize] == ["Phaseolus vulgaris"]
    assert [c["partner"] for c in bean] == ["Zea mays"]
    pair = maize[0]
    assert pair["partner_common_name"] == "Common Bean"
    assert pair["partner_rank_in_city"] == 2                 # the partner's own rank in Lagos
    assert pair["notes"] == "Beans fix nitrogen that feeds maize"
    assert pair["evidence_source"].startswith("VERIFIED") and pair["source_url"]
    assert bean[0]["partner_rank_in_city"] == 1


def test_plant_without_companions_in_a_city_gets_an_empty_list(client):
    assert client.get("/cities/Nairobi/plants/Zea mays/companions").json() == []
    assert client.get("/cities/Lagos/plants/Banana/companions").status_code == 404


def test_plant_catalogue(client):
    assert [p["species"] for p in client.get("/plants").json()] == ["Phaseolus vulgaris", "Zea mays"]
    assert [p["species"] for p in client.get("/plants?search=maize").json()] == ["Zea mays"]
    assert client.get("/plants/Zea mays").json()["common_name"] == "Maize"
    assert client.get("/plants/Banana").status_code == 404


def test_cities_where_a_plant_scores_best(client):
    found = client.get("/plants/Zea mays/cities").json()
    assert [c["city"] for c in found] == ["Lagos", "Nairobi"]
    assert found[0]["country"] == "NG"


def test_ai_context_bundles_facts_and_caveats(client):
    body = client.get("/cities/Lagos/context").json()
    assert body["recommendations_available"] is True
    assert body["top_plants"][0]["species"] == "Zea mays"
    assert body["companions"][0]["species_a"] == "Zea mays"
    assert any("not a yield forecast" in c for c in body["caveats"])
    empty = client.get("/cities/Harare/context").json()
    assert empty["top_plants"] == [] and empty["recommendations_available"] is False


def test_model_info_reports_the_verdict_and_caveats(client):
    body = client.get("/model").json()
    assert "beats the best simple baseline" in body["verdict"]
    assert body["gain_95_percent_range"] == [0.03, 0.14]
    assert body["caveats"]


def test_missing_table_gives_503_without_leaking_sql(client):
    with client.app.state.engine.begin() as c:
        c.execute(text("DROP TABLE ml_species_city_suitability"))
    response = client.get("/cities")
    assert response.status_code == 503
    assert "SELECT" not in response.text


def test_api_only_reads(client):
    assert client.post("/cities").status_code == 405

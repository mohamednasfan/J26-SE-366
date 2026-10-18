from fastapi.testclient import TestClient

from backend.main import app


def test_s2_health_and_search():
    with TestClient(app) as client:
        assert client.get("/health").json()["component"] == "s2_ddi_prediction"
        response = client.get("/api/s2/drugs", params={"q": "metformin"})

    assert response.status_code == 200
    assert response.json()["results"][0]["drug_id"] == "DB00331"


def test_s2_prediction_and_validation():
    with TestClient(app) as client:
        response = client.post(
            "/api/s2/predict",
            json={"drug1_id": "DB00331", "drug2_id": "DB00945", "top_k": 3},
        )
        cold_start = client.post(
            "/api/s2/predict",
            json={
                "drug1_id": "DB00331",
                "drug2_id": "DB00945",
                "top_k": 3,
                "mode": "cold_start",
            },
        )
        invalid = client.post(
            "/api/s2/predict",
            json={"drug1_id": "DB00331", "drug2_id": "DB00331"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intended_use"] == "research_prototype"
    assert len(payload["explanation"]["top_features"]) == 3
    assert cold_start.status_code == 200
    assert cold_start.json()["prediction_mode"] == "cold_start"
    assert invalid.status_code == 422

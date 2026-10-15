from fastapi.testclient import TestClient

from backend.main import app

SAMPLE = {
    "timestamp": "2016-05-10T18:00:00", "lights": 10,
    **{f"T{i}": 21.0 for i in range(1, 10)},
    **{f"RH_{i}": 40.0 for i in range(1, 10)},
    "T_out": 10.0, "Press_mm_hg": 755.0, "RH_out": 80.0,
    "Windspeed": 4.0, "Visibility": 40.0, "Tdewpoint": 4.0,
}


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json()["model_loaded"] is True


def test_predict_returns_positive_number():
    with TestClient(app) as client:
        r = client.post("/predict", json=SAMPLE)
        assert r.status_code == 200
        assert r.json()["predicted_energy_wh"] >= 0


def test_invalid_humidity_rejected():
    with TestClient(app) as client:
        r = client.post("/predict", json={**SAMPLE, "RH_1": 150})
        assert r.status_code == 422

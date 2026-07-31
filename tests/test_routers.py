import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.config import AppConfig

def test_health_check():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

def test_dashboard_page():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Dashboard Overview" in response.text

def test_jobs_page():
    with TestClient(app) as client:
        response = client.get("/jobs")
        assert response.status_code == 200
        assert "Automation Jobs History" in response.text

def test_approvals_page():
    with TestClient(app) as client:
        response = client.get("/approvals")
        assert response.status_code == 200
        assert "Pending Action Approvals" in response.text

def test_analytics_page():
    with TestClient(app) as client:
        response = client.get("/analytics")
        assert response.status_code == 200
        assert "Analytics & Engagement Conversion Dashboard" in response.text

def test_analytics_api():
    with TestClient(app) as client:
        response = client.get("/api/analytics")
        assert response.status_code == 200
        data = response.json()
        assert "total_executions" in data
        assert "success_rate" in data

def test_settings_api():
    with TestClient(app) as client:
        get_res = client.get("/api/settings")
        assert get_res.status_code == 200
        data = get_res.json()
        assert "mode" in data
        assert "active_profile" in data
        assert "generate_custom_connection_notes" in data
        assert "send_custom_connection_notes" in data

        post_res = client.post("/api/settings", json={
            "mode": "approval",
            "active_profile": "work_profile",
            "generate_custom_connection_notes": False,
            "send_custom_connection_notes": False
        })
        assert post_res.status_code == 200
        assert post_res.json()["message"] == "Settings updated and saved permanently."

def test_config_fallback_loading():
    test_path = "temp_non_existent_config.yaml"
    cfg = AppConfig.load(test_path)
    assert cfg.ai_provider in ["gemini", "openai"]
    assert cfg.MODE in ["approval", "automatic"]
    
    p = Path(test_path)
    if p.exists():
        p.unlink()

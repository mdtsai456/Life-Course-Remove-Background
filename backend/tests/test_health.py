"""Tests for GET /health endpoint."""

from __future__ import annotations


class TestHealth:
    def test_health_returns_ok(self, client):
        """All models loaded → 200 with status=ok."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["checks"]["rembg"] is True
        assert data["checks"]["xtts_v2"] is True

    def test_health_missing_rembg(self, client):
        """rembg_session missing → 503."""
        saved = client.app.state.rembg_session
        del client.app.state.rembg_session
        try:
            resp = client.get("/health")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "loading"
            assert data["checks"]["rembg"] is False
            assert data["checks"]["xtts_v2"] is True
        finally:
            client.app.state.rembg_session = saved

    def test_health_missing_tts(self, client):
        """tts_model = None → 503."""
        saved = client.app.state.tts_model
        client.app.state.tts_model = None
        try:
            resp = client.get("/health")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "loading"
            assert data["checks"]["rembg"] is True
            assert data["checks"]["xtts_v2"] is False
        finally:
            client.app.state.tts_model = saved

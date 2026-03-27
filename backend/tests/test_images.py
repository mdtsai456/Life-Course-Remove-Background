"""Tests for /api/remove-background endpoint with model preload."""

from __future__ import annotations


class TestModelPreload:
    def test_session_exists_on_app_state(self, client):
        """After startup, app.state.rembg_session should be set."""
        assert hasattr(client.app.state, "rembg_session")
        assert client.app.state.rembg_session is not None

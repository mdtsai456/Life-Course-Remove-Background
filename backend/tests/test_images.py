"""Tests for /api/remove-background endpoint with model preload."""

from __future__ import annotations

from unittest.mock import patch


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
FAKE_RESULT = b"\x89PNG\r\n\x1a\nfake-result"


class TestModelPreload:
    def test_session_exists_on_app_state(self, client):
        """After startup, app.state.rembg_session should be set."""
        assert hasattr(client.app.state, "rembg_session")
        assert client.app.state.rembg_session is not None


class TestRemoveBackground:
    def test_session_passed_to_remove(self, client):
        """remove() must be called with the preloaded session."""
        with patch("app.routes.images.remove", return_value=FAKE_RESULT) as mock_remove:
            resp = client.post(
                "/api/remove-background",
                files={"file": ("test.png", PNG_HEADER, "image/png")},
            )
        assert resp.status_code == 200
        mock_remove.assert_called_once()
        _, kwargs = mock_remove.call_args
        assert "session" in kwargs
        assert kwargs["session"] is client.app.state.rembg_session

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


class TestRemoveBackgroundValidation:
    def test_reject_unsupported_mime_type(self, client):
        resp = client.post(
            "/api/remove-background",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 415

    def test_reject_oversized_file(self, client):
        big = PNG_HEADER + b"\x00" * (10 * 1024 * 1024)
        resp = client.post(
            "/api/remove-background",
            files={"file": ("big.png", big, "image/png")},
        )
        assert resp.status_code == 413

    def test_reject_bad_magic_bytes(self, client):
        resp = client.post(
            "/api/remove-background",
            files={"file": ("test.png", b"\x00" * 100, "image/png")},
        )
        assert resp.status_code == 415

    def test_success_returns_png(self, client):
        with patch("app.routes.images.remove", return_value=FAKE_RESULT):
            resp = client.post(
                "/api/remove-background",
                files={"file": ("test.png", PNG_HEADER, "image/png")},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == FAKE_RESULT

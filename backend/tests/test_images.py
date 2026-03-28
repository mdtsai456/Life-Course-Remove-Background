"""Tests for /api/remove-background endpoint with model preload."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
FAKE_RESULT = b"\x89PNG\r\n\x1a\nfake-result"


class TestModelPreload:
    def test_session_exists_on_app_state(self, client):
        """After startup, app.state.rembg_session should be set."""
        assert hasattr(client.app.state, "rembg_session")
        assert client.app.state.rembg_session is not None

    def test_startup_fails_when_new_session_raises(self):
        """If new_session() fails, the app should fail to start."""
        mock_rembg = MagicMock()
        mock_rembg.new_session = MagicMock(
            side_effect=RuntimeError("model download failed"),
        )

        mock_torch = MagicMock(name="torch")
        mock_torch.cuda.is_available.return_value = False

        mock_tts_api = MagicMock(name="TTS.api")
        mock_tts_api.TTS = MagicMock(
            name="TTS_class",
            return_value=MagicMock(to=MagicMock(return_value=MagicMock())),
        )

        patches = {
            "rembg": mock_rembg,
            "torch": mock_torch,
            "TTS": MagicMock(name="TTS_module", api=mock_tts_api),
            "TTS.api": mock_tts_api,
        }

        with patch.dict(sys.modules, patches):
            sys.modules.pop("app.main", None)
            sys.modules.pop("app.routes.images", None)

            from app.main import app

            with pytest.raises(RuntimeError, match="model download failed"):
                with TestClient(app):
                    pass

            sys.modules.pop("app.main", None)
            sys.modules.pop("app.routes.images", None)


    def test_returns_503_when_session_not_initialized(self, client):
        """If rembg_session is missing from app.state, return 503."""
        saved = client.app.state.rembg_session
        del client.app.state.rembg_session
        try:
            resp = client.post(
                "/api/remove-background",
                files={"file": ("test.png", PNG_HEADER, "image/png")},
            )
            assert resp.status_code == 503
        finally:
            client.app.state.rembg_session = saved


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
        assert "session" in mock_remove.call_args.kwargs
        assert mock_remove.call_args.kwargs["session"] is client.app.state.rembg_session


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

"""Tests for DOCS_ENABLED toggle."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@contextmanager
def _make_app(docs_enabled: str):
    """Build an app with DOCS_ENABLED set to *docs_enabled*."""
    mock_rembg = MagicMock()
    mock_rembg.new_session.return_value = MagicMock()

    mock_torch = MagicMock(name="torch")
    mock_torch.cuda.is_available.return_value = False

    mock_tts_instance = MagicMock()
    mock_tts_instance.to.return_value = mock_tts_instance
    mock_tts_api = MagicMock(name="TTS.api")
    mock_tts_api.TTS = MagicMock(return_value=mock_tts_instance)

    patches = {
        "rembg": mock_rembg,
        "torch": mock_torch,
        "TTS": MagicMock(api=mock_tts_api),
        "TTS.api": mock_tts_api,
    }

    with patch.dict(sys.modules, patches), \
         patch.dict("os.environ", {"DOCS_ENABLED": docs_enabled}):
        sys.modules.pop("app.main", None)
        sys.modules.pop("app.config", None)
        sys.modules.pop("app.routes.images", None)
        sys.modules.pop("app.routes.threed", None)
        sys.modules.pop("app.routes.voice", None)

        from app.main import app
        with TestClient(app) as c:
            yield c

        sys.modules.pop("app.main", None)
        sys.modules.pop("app.config", None)
        sys.modules.pop("app.routes.images", None)
        sys.modules.pop("app.routes.threed", None)
        sys.modules.pop("app.routes.voice", None)


class TestDocsEnabled:
    def test_docs_available_by_default(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_redoc_available_by_default(self, client):
        resp = client.get("/redoc")
        assert resp.status_code == 200

    def test_docs_disabled_in_production(self):
        with _make_app("false") as c:
            assert c.get("/docs").status_code == 404
            assert c.get("/redoc").status_code == 404

    def test_api_still_works_when_docs_disabled(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with _make_app("false") as c:
            resp = c.post(
                "/api/image-to-3d",
                files={"file": ("m.png", png, "image/png")},
            )
            assert resp.status_code == 200

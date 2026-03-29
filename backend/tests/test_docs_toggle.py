"""Tests for DOCS_ENABLED toggle."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from tests.conftest import PNG_HEADER, _cleanup_modules, _make_mock_tts_api, _make_standard_patches


@contextmanager
def _make_app(docs_enabled: str):
    """Build an app with DOCS_ENABLED set to *docs_enabled*."""
    mock_rembg = MagicMock()
    mock_rembg.new_session.return_value = MagicMock()

    mock_torch = MagicMock(name="torch")
    mock_torch.cuda.is_available.return_value = False

    mock_tts_api, _ = _make_mock_tts_api()

    patches = _make_standard_patches(mock_rembg, mock_torch, mock_tts_api)

    with patch.dict(sys.modules, patches), \
         patch.dict("os.environ", {"DOCS_ENABLED": docs_enabled}):
        _cleanup_modules()

        from app.main import app
        with TestClient(app) as c:
            yield c

        _cleanup_modules()


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
        with _make_app("false") as c:
            resp = c.post(
                "/api/image-to-3d",
                files={"file": ("m.png", PNG_HEADER, "image/png")},
            )
            assert resp.status_code == 200

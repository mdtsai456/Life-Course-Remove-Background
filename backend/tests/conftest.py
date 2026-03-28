"""Shared fixtures for backend tests.

Uses sys.modules patching instead of simple @patch because rembg, torch, and
TTS are imported at module level in main.py.  We need to inject the mocks
*before* the module is imported, not after.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _cleanup_modules():
    """Remove cached app modules so the next import gets a fresh copy."""
    _APP_MODULES = [
        "app.main",
        "app.config",
        "app.routes.images",
        "app.routes.threed",
        "app.routes.voice",
    ]
    for mod in _APP_MODULES:
        sys.modules.pop(mod, None)


def _make_mock_tts_api():
    """Return (mock_tts_api, mock_tts_instance) for sys.modules patching."""
    mock_tts_instance = MagicMock(name="tts_instance")
    mock_tts_instance.to.return_value = mock_tts_instance
    mock_tts_cls = MagicMock(name="TTS_class", return_value=mock_tts_instance)
    mock_tts_api = MagicMock(name="TTS.api")
    mock_tts_api.TTS = mock_tts_cls
    return mock_tts_api, mock_tts_instance


@pytest.fixture()
def client():
    """Yield a TestClient with rembg, torch, and TTS mocked out."""
    mock_session = MagicMock(name="rembg_session")
    mock_rembg = MagicMock()
    mock_rembg.new_session = MagicMock(return_value=mock_session)
    mock_rembg.remove = MagicMock()

    mock_torch = MagicMock(name="torch")
    mock_torch.cuda.is_available.return_value = False

    mock_tts_api, _ = _make_mock_tts_api()

    patches = {
        "rembg": mock_rembg,
        "torch": mock_torch,
        "TTS": MagicMock(name="TTS_module", api=mock_tts_api),
        "TTS.api": mock_tts_api,
    }

    with patch.dict(sys.modules, patches):
        # Force re-import so the app picks up the mocked modules
        _cleanup_modules()

        from app.main import app

        with TestClient(app) as c:
            yield c

        # Clean up re-imported modules so next test gets a fresh import
        _cleanup_modules()

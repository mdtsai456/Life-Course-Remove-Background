"""Shared fixtures for backend tests."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Yield a TestClient with rembg.new_session mocked out."""
    mock_session = MagicMock(name="rembg_session")

    # Create a mock rembg module so we never import the real one
    # (which requires onnxruntime).
    mock_rembg = MagicMock()
    mock_rembg.new_session = MagicMock(return_value=mock_session)
    mock_rembg.remove = MagicMock()

    with patch.dict(sys.modules, {"rembg": mock_rembg}):
        # Force re-import so the app picks up the mocked module
        sys.modules.pop("app.main", None)
        sys.modules.pop("app.routes.images", None)

        from app.main import app

        with TestClient(app) as c:
            yield c

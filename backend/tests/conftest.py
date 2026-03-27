"""Shared fixtures for backend tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Yield a TestClient with rembg.new_session mocked out."""
    mock_session = MagicMock(name="rembg_session")
    with patch("rembg.new_session", return_value=mock_session):
        from app.main import app

        with TestClient(app) as c:
            yield c

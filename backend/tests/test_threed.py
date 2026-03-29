"""Tests for /api/image-to-3d endpoint and _make_mock_glb helper."""

from __future__ import annotations

import json
import struct

from app.routes.threed import _make_mock_glb
from tests.conftest import PNG_HEADER


# ===========================================================================
# _make_mock_glb unit tests
# ===========================================================================
class TestMakeMockGlb:
    def test_glb_magic_and_version(self):
        glb = _make_mock_glb()
        magic, version, length = struct.unpack_from("<III", glb, 0)
        assert magic == 0x46546C67  # "glTF"
        assert version == 2
        assert length == len(glb)

    def test_json_chunk_is_valid(self):
        glb = _make_mock_glb()
        chunk_len, chunk_type = struct.unpack_from("<II", glb, 12)
        assert chunk_type == 0x4E4F534A  # "JSON"
        json_bytes = glb[20 : 20 + chunk_len]
        data = json.loads(json_bytes)
        assert data["asset"]["version"] == "2.0"
        assert "scenes" in data


# ===========================================================================
# /api/image-to-3d endpoint tests
# ===========================================================================
class TestImageTo3dValidation:
    def test_accept_mismatched_mime_with_valid_magic(self, client):
        """MIME says image/jpeg but content is valid PNG → accept (magic bytes win)."""
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.jpg", PNG_HEADER, "image/jpeg")},
        )
        assert resp.status_code == 200

    def test_accept_octet_stream_with_valid_magic(self, client):
        """MIME is generic but content is valid PNG → accept."""
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "application/octet-stream")},
        )
        assert resp.status_code == 200

    def test_reject_oversized_file_via_size_header(self, client):
        big = PNG_HEADER + b"\x00" * (10 * 1024 * 1024)
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("big.png", big, "image/png")},
        )
        assert resp.status_code == 413
        assert "10 MB" in resp.json()["detail"]

    def test_reject_bad_magic_bytes(self, client):
        """MIME is image/png but content is not actually PNG."""
        fake = b"\x00" * 200
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", fake, "image/png")},
        )
        assert resp.status_code == 415
        assert "image/png" in resp.json()["detail"]

    def test_success_returns_glb(self, client):
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "model/gltf-binary"
        assert resp.headers["content-disposition"] == 'attachment; filename="model.glb"'
        # Verify response is valid GLB
        magic = struct.unpack_from("<I", resp.content, 0)[0]
        assert magic == 0x46546C67

    def test_security_header_present(self, client):
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert resp.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"

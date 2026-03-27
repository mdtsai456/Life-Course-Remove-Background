"""Tests for the /api/clone-voice endpoint and _detect_audio_type helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydub.exceptions import CouldntDecodeError

from app.routes.voice import AudioConversionError, _convert_to_wav, _detect_audio_type

# ---------------------------------------------------------------------------
# Magic bytes helpers
# ---------------------------------------------------------------------------
WEBM_HEADER = b"\x1a\x45\xdf\xa3" + b"\x00" * 4  # EBML magic + padding to 8 bytes
OGG_HEADER = b"OggS" + b"\x00" * 4
# MP4: 4 bytes size + "ftyp" at offset 4
MP4_HEADER = b"\x00\x00\x00\x18" + b"ftyp" + b"isom" + b"\x00" * 4

WAV_STUB = b"RIFF\x00\x00\x00\x00WAVEfmt "


def _make_audio(header: bytes, size: int = 1024) -> bytes:
    """Return header padded to *size* bytes."""
    return header + b"\x00" * (size - len(header))


# ===========================================================================
# _detect_audio_type unit tests
# ===========================================================================
class TestDetectAudioType:
    def test_webm(self):
        assert _detect_audio_type(_make_audio(WEBM_HEADER)) == "audio/webm"

    def test_ogg(self):
        assert _detect_audio_type(_make_audio(OGG_HEADER)) == "audio/ogg"

    def test_mp4_ftyp_at_offset_4(self):
        assert _detect_audio_type(_make_audio(MP4_HEADER)) == "audio/mp4"

    def test_mp4_ftyp_must_be_at_offset_4_not_0(self):
        """ftyp at offset 0 should NOT be detected as MP4."""
        bad = b"ftyp" + b"\x00" * 4
        assert _detect_audio_type(bad) is None

    def test_too_short_returns_none(self):
        assert _detect_audio_type(b"\x1a\x45\xdf") is None  # 3 bytes
        assert _detect_audio_type(b"") is None
        assert _detect_audio_type(b"\x00" * 7) is None

    def test_exactly_8_bytes(self):
        assert _detect_audio_type(WEBM_HEADER) == "audio/webm"

    def test_unknown_magic_returns_none(self):
        assert _detect_audio_type(b"\x00" * 16) is None
        assert _detect_audio_type(b"RIFF\x00\x00\x00\x00") is None


# ===========================================================================
# _convert_to_wav unit tests
# ===========================================================================
class TestConvertToWav:
    def test_success(self):
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_audio = MagicMock()
            mock_audio.raw_data = b"\x00" * 100
            mock_cls.from_file.return_value = mock_audio

            def _export_side_effect(buf, **_kwargs):
                buf.write(WAV_STUB)

            mock_audio.export.side_effect = _export_side_effect

            result = _convert_to_wav(b"fake-audio", "webm")
            assert result == WAV_STUB
            mock_cls.from_file.assert_called_once()

    def test_decode_error(self):
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_cls.from_file.side_effect = CouldntDecodeError("bad file")
            with pytest.raises(AudioConversionError, match="無法解碼音訊檔案"):
                _convert_to_wav(b"bad-audio", "webm")

    def test_ffmpeg_not_found(self):
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_cls.from_file.side_effect = FileNotFoundError("ffmpeg not found")
            with pytest.raises(FileNotFoundError):
                _convert_to_wav(b"some-audio", "webm")

    def test_oversized_pcm(self):
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_audio = MagicMock()
            mock_audio.raw_data = b"\x00" * (50 * 1024 * 1024 + 1)
            mock_cls.from_file.return_value = mock_audio
            with pytest.raises(AudioConversionError, match="音訊解壓後超過大小限制"):
                _convert_to_wav(b"some-audio", "webm")


# ===========================================================================
# /api/clone-voice endpoint tests
# ===========================================================================
class TestCloneVoiceEndpoint:
    # -- success --
    def test_success_webm(self, client):
        audio = _make_audio(WEBM_HEADER)
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_seg = MagicMock()
            mock_seg.raw_data = b"\x00" * 100
            mock_cls.from_file.return_value = mock_seg

            def _export_side_effect(buf, **_kwargs):
                buf.write(WAV_STUB)

            mock_seg.export.side_effect = _export_side_effect

            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.webm", audio, "audio/webm")},
                data={"text": "hello"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert resp.headers["content-disposition"] == 'attachment; filename="cloned.wav"'
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.content == WAV_STUB

    def test_success_ogg(self, client):
        audio = _make_audio(OGG_HEADER)
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_seg = MagicMock()
            mock_seg.raw_data = b"\x00" * 100
            mock_cls.from_file.return_value = mock_seg

            def _export_side_effect(buf, **_kwargs):
                buf.write(WAV_STUB)

            mock_seg.export.side_effect = _export_side_effect

            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.ogg", audio, "audio/ogg")},
                data={"text": "hello"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert resp.headers["content-disposition"] == 'attachment; filename="cloned.wav"'

    def test_success_mp4(self, client):
        audio = _make_audio(MP4_HEADER)
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_seg = MagicMock()
            mock_seg.raw_data = b"\x00" * 100
            mock_cls.from_file.return_value = mock_seg

            def _export_side_effect(buf, **_kwargs):
                buf.write(WAV_STUB)

            mock_seg.export.side_effect = _export_side_effect

            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.m4a", audio, "audio/mp4")},
                data={"text": "hello"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert resp.headers["content-disposition"] == 'attachment; filename="cloned.wav"'

    # -- MIME type validation (415) --
    def test_reject_unsupported_mime_type(self, client):
        audio = _make_audio(WEBM_HEADER)
        resp = client.post(
            "/api/clone-voice",
            files={"file": ("rec.wav", audio, "audio/wav")},
            data={"text": "hello"},
        )
        assert resp.status_code == 415
        assert "Unsupported audio type" in resp.json()["detail"]

    def test_reject_mime_with_codec_suffix(self, client):
        """audio/webm;codecs=opus should still be accepted (stripped to audio/webm)."""
        audio = _make_audio(WEBM_HEADER)
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_seg = MagicMock()
            mock_seg.raw_data = b"\x00" * 100
            mock_cls.from_file.return_value = mock_seg

            def _export_side_effect(buf, **_kwargs):
                buf.write(WAV_STUB)

            mock_seg.export.side_effect = _export_side_effect

            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.webm", audio, "audio/webm;codecs=opus")},
                data={"text": "hello"},
            )
        assert resp.status_code == 200

    # -- text validation (400) --
    def test_reject_missing_text(self, client):
        audio = _make_audio(WEBM_HEADER)
        resp = client.post(
            "/api/clone-voice",
            files={"file": ("rec.webm", audio, "audio/webm")},
        )
        assert resp.status_code == 400
        assert "Text must not be empty" in resp.json()["detail"]

    def test_reject_empty_text(self, client):
        audio = _make_audio(WEBM_HEADER)
        resp = client.post(
            "/api/clone-voice",
            files={"file": ("rec.webm", audio, "audio/webm")},
            data={"text": ""},
        )
        assert resp.status_code == 400

    def test_reject_whitespace_only_text(self, client):
        audio = _make_audio(WEBM_HEADER)
        resp = client.post(
            "/api/clone-voice",
            files={"file": ("rec.webm", audio, "audio/webm")},
            data={"text": "   "},
        )
        assert resp.status_code == 400

    # -- file size validation (413) --
    def test_reject_oversized_file(self, client):
        big = _make_audio(WEBM_HEADER, size=10 * 1024 * 1024 + 1)
        resp = client.post(
            "/api/clone-voice",
            files={"file": ("rec.webm", big, "audio/webm")},
            data={"text": "hello"},
        )
        assert resp.status_code == 413
        assert "File too large" in resp.json()["detail"]

    # -- magic bytes validation (415) --
    def test_reject_bad_magic_bytes(self, client):
        """Valid MIME but file content doesn't match any known audio format."""
        fake = b"\x00" * 1024
        resp = client.post(
            "/api/clone-voice",
            files={"file": ("rec.webm", fake, "audio/webm")},
            data={"text": "hello"},
        )
        assert resp.status_code == 415
        assert "valid audio file" in resp.json()["detail"]

    # -- conversion error paths --
    def test_conversion_failure_returns_422(self, client):
        audio = _make_audio(WEBM_HEADER)
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_cls.from_file.side_effect = CouldntDecodeError("bad")
            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.webm", audio, "audio/webm")},
                data={"text": "hello"},
            )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "無法解碼音訊檔案。"

    def test_oversized_pcm_returns_422(self, client):
        audio = _make_audio(WEBM_HEADER)
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_seg = MagicMock()
            mock_seg.raw_data = b"\x00" * (50 * 1024 * 1024 + 1)
            mock_cls.from_file.return_value = mock_seg
            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.webm", audio, "audio/webm")},
                data={"text": "hello"},
            )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "音訊解壓後超過大小限制。"

    def test_export_failure_returns_422(self, client):
        audio = _make_audio(WEBM_HEADER)
        with patch("app.routes.voice.AudioSegment") as mock_cls:
            mock_seg = MagicMock()
            mock_seg.raw_data = b"\x00" * 100
            mock_cls.from_file.return_value = mock_seg
            mock_seg.export.side_effect = Exception("encode failed")
            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.webm", audio, "audio/webm")},
                data={"text": "hello"},
            )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "音訊編碼失敗。"

    def test_ffmpeg_missing_returns_503(self, client):
        audio = _make_audio(WEBM_HEADER)
        with patch("app.routes.voice._convert_to_wav", side_effect=FileNotFoundError("ffmpeg")):
            resp = client.post(
                "/api/clone-voice",
                files={"file": ("rec.webm", audio, "audio/webm")},
                data={"text": "hello"},
            )
        assert resp.status_code == 503
        assert resp.json()["detail"] == "音訊轉換服務暫時無法使用。"

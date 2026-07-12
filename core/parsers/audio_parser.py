from pathlib import Path

try:
    from mutagen import File as MutagenFile
except Exception:  # pragma: no cover - optional dependency
    MutagenFile = None


class AudioParser:
    """Parser for audio files using Mutagen when available."""

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        metadata = {"name": path.name, "size_bytes": path.stat().st_size, "parser": "audio_parser"}

        if MutagenFile is not None:
            try:
                audio = MutagenFile(file_path)
                if audio is not None:
                    tags = self._extract_tags(audio)
                    if tags:
                        metadata["tags"] = tags

                    tech_info = self._extract_technical_info(audio)
                    if tech_info:
                        metadata["technical"] = tech_info
                else:
                    metadata["note"] = "Format non reconnu par Mutagen (aucun tag disponible)."
            except Exception as exc:  # pragma: no cover - runtime dependency may be absent
                metadata["error"] = str(exc)

        return {"file": file_path, "type": "audio", "metadata": metadata}

    # ------------------------------------------------------------------
    # Tags (ID3 for MP3, Vorbis comments for FLAC/OGG, MP4 atoms for M4A...)
    # ------------------------------------------------------------------
    def _extract_tags(self, audio) -> dict:
        tags = {}
        try:
            items = audio.items() if hasattr(audio, "items") else []
        except Exception:
            items = []

        for key, value in items:
            if not key:
                continue
            cleaned = self._clean_value(value)
            if cleaned is not None:
                tags[str(key)] = cleaned
        return tags

    def _clean_value(self, value):
        """Make tag values JSON/display friendly.

        Handles the three main shapes Mutagen hands back depending on
        format:
        - ID3 Frame objects (MP3): have a `.text` attribute (list of str),
          except picture frames (APIC) which carry binary `.data`.
        - Plain lists of strings (FLAC/OGG Vorbis comments).
        - MP4 atoms: tuples, MP4Cover (binary), MP4FreeForm, or plain values.
        """
        # ID3 picture frame (APIC) or MP4 cover art: don't dump raw binary
        if hasattr(value, "data") and isinstance(getattr(value, "data"), (bytes, bytearray)):
            return f"<image de couverture, {len(value.data)} octets>"

        # ID3 text frame (TIT2, TPE1, TALB, TDRC...) exposes `.text`
        if hasattr(value, "text"):
            text_value = value.text
            return self._clean_value(text_value)

        if isinstance(value, bytes):
            if len(value) > 200:
                return f"<binary data, {len(value)} bytes>"
            try:
                return value.decode("utf-8", errors="replace").strip("\x00")
            except Exception:
                return value.hex()

        if isinstance(value, (list, tuple)):
            cleaned = [self._clean_value(item) for item in value]
            cleaned = [c for c in cleaned if c not in (None, "")]
            if not cleaned:
                return None
            # Collapse single-item lists like ["Song Title"] -> "Song Title"
            return cleaned[0] if len(cleaned) == 1 else cleaned

        if not isinstance(value, (str, int, float, bool, type(None))):
            try:
                return str(value)
            except Exception:
                return None

        return value

    # ------------------------------------------------------------------
    # Technical info (duration, bitrate, sample rate, channels...)
    # ------------------------------------------------------------------
    def _extract_technical_info(self, audio) -> dict:
        info = getattr(audio, "info", None)
        if info is None:
            return {}

        tech = {}
        for attr in ("length", "bitrate", "sample_rate", "channels", "bits_per_sample", "codec", "codec_description", "mode"):
            if hasattr(info, attr):
                value = getattr(info, attr)
                if value not in (None, ""):
                    tech[attr] = self._clean_value(value)

        if "length" in tech:
            try:
                seconds = float(tech["length"])
                minutes, secs = divmod(int(seconds), 60)
                hours, minutes = divmod(minutes, 60)
                tech["duration_formatted"] = (
                    f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
                )
            except (TypeError, ValueError):
                pass

        return tech
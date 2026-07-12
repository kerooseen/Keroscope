import re
from pathlib import Path

try:
    from mutagen import File as MutagenFile
except Exception:  # pragma: no cover - optional dependency
    MutagenFile = None

# ISO 6709 location string, as written by iPhones/Android phones in the
# QuickTime "©xyz" atom, e.g. "+37.3346-122.0090/" or with altitude
# "+48.8558+002.2922+035.000/"
_ISO6709_RE = re.compile(
    r"^(?P<lat>[+-]\d+(?:\.\d+)?)(?P<lon>[+-]\d+(?:\.\d+)?)(?P<alt>[+-]\d+(?:\.\d+)?)?/?$"
)


class VideoParser:
    """Parser for video files using Mutagen when available.

    Note: Mutagen's container support for video is limited to MP4/MOV
    (QuickTime) style containers. Formats like .avi or .mkv will simply
    return no tags — this is a Mutagen limitation, not a bug.
    """

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        metadata = {"name": path.name, "size_bytes": path.stat().st_size, "parser": "video_parser"}

        if MutagenFile is not None:
            try:
                video = MutagenFile(file_path)
                if video is not None:
                    tags = self._extract_tags(video)
                    if tags:
                        metadata["tags"] = tags

                    tech_info = self._extract_technical_info(video)
                    if tech_info:
                        metadata["technical"] = tech_info

                    gps = self._extract_gps(tags)
                    if gps:
                        metadata["gps"] = gps
                else:
                    metadata["note"] = "Format non reconnu par Mutagen (aucun tag disponible)."
            except Exception as exc:  # pragma: no cover - runtime dependency may be absent
                metadata["error"] = str(exc)

        return {"file": file_path, "type": "video", "metadata": metadata}

    # ------------------------------------------------------------------
    # Tags (container metadata)
    # ------------------------------------------------------------------
    def _extract_tags(self, video) -> dict:
        tags = {}
        try:
            items = video.items() if hasattr(video, "items") else []
        except Exception:
            items = []

        for key, value in items:
            if not key:
                continue
            tags[str(key)] = self._clean_value(value)
        return tags

    def _clean_value(self, value):
        """Make tag values JSON/display friendly, handling Mutagen's
        MP4Cover, MP4FreeForm, tuples, bytes, and lists of any of these.
        """
        if isinstance(value, (list, tuple)):
            cleaned = [self._clean_value(item) for item in value]
            # Collapse single-item lists like ["Xiaomi"] -> "Xiaomi" for readability
            return cleaned[0] if len(cleaned) == 1 else cleaned

        if isinstance(value, bytes):
            # Covers (album/thumbnail art) and raw binary atoms: don't dump
            # megabytes of binary into the metadata view.
            return f"<binary data, {len(value)} bytes>"

        if not isinstance(value, (str, int, float, bool, type(None))):
            try:
                return str(value)
            except Exception:
                return "<unreadable value>"

        return value

    # ------------------------------------------------------------------
    # Technical info (duration, bitrate, codec...)
    # ------------------------------------------------------------------
    def _extract_technical_info(self, video) -> dict:
        info = getattr(video, "info", None)
        if info is None:
            return {}

        tech = {}
        for attr in ("length", "bitrate", "codec", "codec_description", "sample_rate", "channels", "bits_per_sample"):
            if hasattr(info, attr):
                value = getattr(info, attr)
                if value not in (None, ""):
                    tech[attr] = self._clean_value(value)

        if "length" in tech:
            try:
                seconds = float(tech["length"])
                minutes, secs = divmod(int(seconds), 60)
                hours, minutes = divmod(minutes, 60)
                tech["duration_formatted"] = f"{hours:02d}:{minutes:02d}:{secs:02d}"
            except (TypeError, ValueError):
                pass

        return tech

    # ------------------------------------------------------------------
    # GPS extraction (ISO 6709 location atom, e.g. QuickTime "©xyz")
    # ------------------------------------------------------------------
    def _extract_gps(self, tags: dict) -> dict | None:
        if not tags:
            return None

        # Different phones/apps use slightly different atom names for the
        # same ISO 6709 location string.
        candidate_keys = ("©xyz", "location", "com.apple.quicktime.location.iso6709", "----:com.apple.quicktime:location.ISO6709")
        raw_location = None
        for key in candidate_keys:
            if key in tags and tags[key]:
                raw_location = tags[key]
                break

        if not isinstance(raw_location, str):
            return None

        match = _ISO6709_RE.match(raw_location.strip())
        if not match:
            return None

        try:
            lat = float(match.group("lat"))
            lon = float(match.group("lon"))
        except (TypeError, ValueError):
            return None

        result = {
            "latitude": round(lat, 7),
            "longitude": round(lon, 7),
            "google_maps_url": f"https://www.google.com/maps?q={lat:.7f},{lon:.7f}",
            "raw": raw_location,
        }

        alt_str = match.group("alt")
        if alt_str:
            try:
                result["altitude"] = round(float(alt_str), 2)
            except (TypeError, ValueError):
                pass

        return result
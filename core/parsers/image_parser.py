from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except Exception:  # pragma: no cover - optional dependency
    Image = None
    TAGS = {}
    GPSTAGS = {}


class ImageParser:
    """Parser for image files with EXIF and GPS support."""

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        metadata = {
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "parser": "image_parser",
        }

        if Image is not None:
            try:
                with Image.open(file_path) as img:
                    metadata["format"] = img.format
                    metadata["mode"] = img.mode
                    metadata["size_px"] = {"width": img.width, "height": img.height}

                    exif = img.getexif()
                    if exif:
                        readable_exif = self._readable_exif(exif)
                        if readable_exif:
                            metadata["exif"] = readable_exif

                        gps_data = self._extract_gps(exif)
                        if gps_data:
                            metadata["gps"] = gps_data

            except Exception as exc:  # pragma: no cover - runtime dependency may be absent
                metadata["error"] = str(exc)

        return {"file": file_path, "type": "image", "metadata": metadata}

    # ------------------------------------------------------------------
    # EXIF (non-GPS) fields, resolved to human-readable tag names
    # ------------------------------------------------------------------
    def _readable_exif(self, exif) -> dict:
        result = {}
        for tag_id, value in exif.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            if tag_name == "GPSInfo":
                continue  # handled separately by _extract_gps
            result[tag_name] = self._clean_value(value)
        return result

    def _clean_value(self, value):
        """Recursively make EXIF values JSON/display friendly.

        Pillow returns several types that json.dumps() cannot handle on its
        own: IFDRational, bytes, and tuples/lists that contain them (very
        common for FNumber, ExposureTime, FocalLength, GPS coordinates...).
        """
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="replace").strip("\x00")
            except Exception:
                return value.hex()

        # IFDRational (and any other Pillow rational type) -> plain number
        if hasattr(value, "numerator") and hasattr(value, "denominator"):
            try:
                if value.denominator == 0:
                    return None
                return round(float(value), 6)
            except Exception:
                return str(value)

        if isinstance(value, (tuple, list)):
            return [self._clean_value(item) for item in value]

        if isinstance(value, dict):
            return {str(k): self._clean_value(v) for k, v in value.items()}

        # Fallback: anything else not natively JSON-serializable becomes a string
        if not isinstance(value, (str, int, float, bool, type(None))):
            return str(value)

        return value

    # ------------------------------------------------------------------
    # GPS extraction
    # ------------------------------------------------------------------
    def _extract_gps(self, exif) -> dict | None:
        """Extract and convert GPS EXIF data into a usable dict.

        Returns something like:
        {
            "latitude": 48.8583736,
            "longitude": 2.2922926,
            "altitude": 35.0,
            "latitude_ref": "N",
            "longitude_ref": "E",
            "timestamp": "14:23:05",
            "date": "2024:06:01",
            "google_maps_url": "https://www.google.com/maps?q=48.8583736,2.2922926",
            "raw": {...}
        }
        """
        try:
            gps_ifd = exif.get_ifd(0x8825)  # IFD tag for GPSInfo
        except Exception:
            gps_ifd = None

        if not gps_ifd:
            return None

        gps_named = {GPSTAGS.get(key, key): value for key, value in gps_ifd.items()}

        result: dict = {"raw": {k: self._clean_value(v) for k, v in gps_named.items()}}

        lat = self._convert_to_degrees(gps_named.get("GPSLatitude"))
        lon = self._convert_to_degrees(gps_named.get("GPSLongitude"))
        lat_ref = gps_named.get("GPSLatitudeRef")
        lon_ref = gps_named.get("GPSLongitudeRef")

        if lat is not None and lon is not None:
            if lat_ref in ("S", b"S"):
                lat = -lat
            if lon_ref in ("W", b"W"):
                lon = -lon

            result["latitude"] = round(lat, 7)
            result["longitude"] = round(lon, 7)
            result["latitude_ref"] = self._clean_value(lat_ref)
            result["longitude_ref"] = self._clean_value(lon_ref)
            result["google_maps_url"] = f"https://www.google.com/maps?q={lat:.7f},{lon:.7f}"

        altitude = gps_named.get("GPSAltitude")
        if altitude is not None:
            try:
                alt_value = float(altitude)
                alt_ref = gps_named.get("GPSAltitudeRef", 0)
                # AltitudeRef == 1 means "below sea level"
                if alt_ref in (1, b"\x01"):
                    alt_value = -alt_value
                result["altitude"] = round(alt_value, 2)
            except (TypeError, ValueError):
                pass

        timestamp = gps_named.get("GPSTimeStamp")
        if timestamp is not None:
            try:
                h, m, s = (float(v) for v in timestamp)
                result["timestamp"] = f"{int(h):02d}:{int(m):02d}:{s:05.2f}"
            except (TypeError, ValueError):
                pass

        date_stamp = gps_named.get("GPSDateStamp")
        if date_stamp is not None:
            result["date"] = self._clean_value(date_stamp)

        speed = gps_named.get("GPSSpeed")
        if speed is not None:
            try:
                result["speed"] = round(float(speed), 2)
                result["speed_ref"] = self._clean_value(gps_named.get("GPSSpeedRef"))
            except (TypeError, ValueError):
                pass

        img_direction = gps_named.get("GPSImgDirection")
        if img_direction is not None:
            try:
                result["direction"] = round(float(img_direction), 2)
                result["direction_ref"] = self._clean_value(gps_named.get("GPSImgDirectionRef"))
            except (TypeError, ValueError):
                pass

        # If we found nothing beyond the raw dump, still return raw for debugging.
        return result

    @staticmethod
    def _convert_to_degrees(value) -> float | None:
        """Convert a GPS coordinate stored as ((d,1),(m,1),(s,100)) style
        rationals (or plain floats, depending on Pillow version) into
        decimal degrees.
        """
        if value is None:
            return None
        try:
            d, m, s = value
            d = float(d)
            m = float(m)
            s = float(s)
            return d + (m / 60.0) + (s / 3600.0)
        except (TypeError, ValueError):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
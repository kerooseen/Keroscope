from copy import deepcopy

from core.parsers.archive_parser import ArchiveParser
from core.parsers.audio_parser import AudioParser
from core.parsers.document_parser import DocumentParser
from core.parsers.image_parser import ImageParser
from core.parsers.video_parser import VideoParser


class Extractor:
    """Routes incoming files to the correct parser."""

    SENSITIVE_KEYWORDS = {
        "gps", "latitude", "longitude", "altitude",
        "author", "artist", "creator", "software", "producer",
        "location", "city", "country",
        "email", "phone", "imei", "serial",
        "device", "make", "model", "camera",
        "date", "created", "modified", "generator",
    }

    def __init__(self) -> None:
        self.parsers = {
            "image": ImageParser(),
            "document": DocumentParser(),
            "audio": AudioParser(),
            "video": VideoParser(),
            "archive": ArchiveParser(),
        }

    def extract(self, file_path: str) -> dict:
        kind = self.detect_type(file_path)
        parser = self.parsers.get(kind)
        if parser is None:
            return {"file": file_path, "type": "unknown", "metadata": {}, "sensitive_fields": []}

        record = parser.parse(file_path)
        metadata = record.get("metadata", {})
        record["sensitive_fields"] = self.detect_sensitive_fields(metadata)
        return record

    def detect_type(self, file_path: str) -> str:
        extension = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""

        if extension in {"jpg", "jpeg", "png", "gif", "bmp", "tiff"}:
            return "image"
        if extension in {"pdf", "doc", "docx", "txt", "odt"}:
            return "document"
        if extension in {"mp3", "wav", "ogg", "flac"}:
            return "audio"
        if extension in {"mp4", "avi", "mov", "mkv"}:
            return "video"
        if extension in {"zip", "rar", "7z", "tar", "gz"}:
            return "archive"
        return "unknown"

    def detect_sensitive_fields(self, metadata: dict) -> list[str]:
        matches: list[str] = []
        for key in self._flatten_keys(metadata):
            if any(keyword in key.lower() for keyword in self.SENSITIVE_KEYWORDS):
                matches.append(key)
        return sorted(set(matches))

    def clean_sensitive_metadata(self, record: dict) -> dict:
        cleaned = deepcopy(record)
        cleaned["metadata"] = self._sanitize_metadata(cleaned.get("metadata", {}))
        cleaned["sensitive_fields"] = []
        return cleaned

    def _flatten_keys(self, data: object, prefix: str = "") -> list[str]:
        if isinstance(data, dict):
            keys: list[str] = []
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else str(key)
                keys.append(full_key)
                keys.extend(self._flatten_keys(value, full_key))
            return keys
        return []

    def _sanitize_metadata(self, data: object) -> object:
        if isinstance(data, dict):
            sanitized: dict[str, object] = {}
            for key, value in data.items():
                if any(keyword in key.lower() for keyword in self.SENSITIVE_KEYWORDS):
                    sanitized[key] = "[supprimé]"
                else:
                    sanitized[key] = self._sanitize_metadata(value)
            return sanitized
        if isinstance(data, list):
            return [self._sanitize_metadata(item) for item in data]
        return data
import tarfile
import zipfile
from pathlib import Path

try:
    import rarfile
except Exception:  # pragma: no cover - optional dependency
    rarfile = None

try:
    import py7zr
except Exception:  # pragma: no cover - optional dependency
    py7zr = None

_MAX_ENTRIES_LISTED = 20


class ArchiveParser:
    """Parser for common archive formats (zip, tar/gz/bz2, and optionally rar/7z)."""

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        metadata = {"name": path.name, "size_bytes": path.stat().st_size, "parser": "archive_parser"}
        extension = path.suffix.lower()

        try:
            if extension == ".zip":
                self._parse_zip(file_path, metadata)
            elif extension in {".tar", ".gz", ".tgz", ".bz2"}:
                self._parse_tar(file_path, metadata)
            elif extension == ".rar":
                self._parse_rar(file_path, metadata)
            elif extension == ".7z":
                self._parse_7z(file_path, metadata)
        except Exception as exc:
            # Never let a corrupted/password-protected/unsupported archive
            # crash the whole batch — record the error and move on.
            metadata["error"] = str(exc)

        return {"file": file_path, "type": "archive", "metadata": metadata}

    # ------------------------------------------------------------------
    # ZIP
    # ------------------------------------------------------------------
    def _parse_zip(self, file_path: str, metadata: dict) -> None:
        with zipfile.ZipFile(file_path) as archive:
            infos = archive.infolist()
            metadata["count"] = len(infos)
            metadata["entries"] = [info.filename for info in infos[:_MAX_ENTRIES_LISTED]]
            metadata["entries_truncated"] = len(infos) > _MAX_ENTRIES_LISTED

            if archive.comment:
                metadata["comment"] = self._decode_bytes(archive.comment)

            encrypted_count = sum(1 for info in infos if info.flag_bits & 0x1)
            if encrypted_count:
                metadata["encrypted_entries"] = encrypted_count
                metadata["password_protected"] = True

            total_compressed = sum(info.compress_size for info in infos)
            total_uncompressed = sum(info.file_size for info in infos)
            metadata["total_compressed_size"] = total_compressed
            metadata["total_uncompressed_size"] = total_uncompressed

    # ------------------------------------------------------------------
    # TAR / TAR.GZ / TGZ / TAR.BZ2
    # ------------------------------------------------------------------
    def _parse_tar(self, file_path: str, metadata: dict) -> None:
        with tarfile.open(file_path, "r:*") as archive:
            members = archive.getmembers()
            metadata["count"] = len(members)
            metadata["entries"] = [member.name for member in members[:_MAX_ENTRIES_LISTED]]
            metadata["entries_truncated"] = len(members) > _MAX_ENTRIES_LISTED
            metadata["total_uncompressed_size"] = sum(member.size for member in members)

    # ------------------------------------------------------------------
    # RAR (optional dependency: rarfile, itself needs the `unrar`/`unar`
    # command-line tool installed on the system to actually work)
    # ------------------------------------------------------------------
    def _parse_rar(self, file_path: str, metadata: dict) -> None:
        if rarfile is None:
            metadata["note"] = (
                "Le module 'rarfile' n'est pas installé : impossible d'analyser ce .rar. "
                "Installez-le avec `pip install rarfile` (nécessite aussi l'utilitaire "
                "'unrar' sur le système)."
            )
            return

        with rarfile.RarFile(file_path) as archive:
            infos = archive.infolist()
            metadata["count"] = len(infos)
            metadata["entries"] = [info.filename for info in infos[:_MAX_ENTRIES_LISTED]]
            metadata["entries_truncated"] = len(infos) > _MAX_ENTRIES_LISTED
            metadata["password_protected"] = archive.needs_password()
            metadata["total_uncompressed_size"] = sum(info.file_size for info in infos)

    # ------------------------------------------------------------------
    # 7Z (optional dependency: py7zr)
    # ------------------------------------------------------------------
    def _parse_7z(self, file_path: str, metadata: dict) -> None:
        if py7zr is None:
            metadata["note"] = (
                "Le module 'py7zr' n'est pas installé : impossible d'analyser ce .7z. "
                "Installez-le avec `pip install py7zr`."
            )
            return

        with py7zr.SevenZipFile(file_path, mode="r") as archive:
            names = archive.getnames()
            metadata["count"] = len(names)
            metadata["entries"] = names[:_MAX_ENTRIES_LISTED]
            metadata["entries_truncated"] = len(names) > _MAX_ENTRIES_LISTED
            metadata["password_protected"] = archive.needs_password()

    # ------------------------------------------------------------------
    @staticmethod
    def _decode_bytes(value) -> str:
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="replace").strip("\x00")
            except Exception:
                return value.hex()
        return str(value)
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path

try:
    from docx import Document as DocxDocument
except Exception:  # pragma: no cover - optional dependency
    DocxDocument = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None

# Namespaces used inside an .odt's META-INF/meta.xml (OpenDocument format)
_ODF_NAMESPACES = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
}


class DocumentParser:
    """Parser for documents such as PDF, DOCX, ODT and plain text files."""

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        metadata = {"name": path.name, "size_bytes": path.stat().st_size, "parser": "document_parser"}
        extension = path.suffix.lower()

        if extension == ".pdf":
            self._parse_pdf(file_path, metadata)
        elif extension == ".docx":
            self._parse_docx(file_path, metadata)
        elif extension == ".odt":
            self._parse_odt(file_path, metadata)
        elif extension == ".txt":
            self._parse_txt(path, metadata)
        elif extension == ".doc":
            metadata["note"] = (
                "Format .doc (Word 97-2003 binaire) non pris en charge pour l'extraction "
                "détaillée des métadonnées. Convertissez en .docx pour une analyse complète."
            )

        return {"file": file_path, "type": "document", "metadata": metadata}

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    def _parse_pdf(self, file_path: str, metadata: dict) -> None:
        if PdfReader is None:
            metadata["note"] = "pypdf n'est pas installé : impossible d'analyser ce PDF."
            return

        try:
            reader = PdfReader(file_path)
            info = reader.metadata or {}
            pdf_meta = {
                "pages": len(reader.pages),
                "title": self._clean_value(info.get("/Title")),
                "author": self._clean_value(info.get("/Author")),
                "subject": self._clean_value(info.get("/Subject")),
                "keywords": self._clean_value(info.get("/Keywords")),
                "creator": self._clean_value(info.get("/Creator")),
                "producer": self._clean_value(info.get("/Producer")),
                "creation_date": self._clean_value(info.get("/CreationDate")),
                "modification_date": self._clean_value(info.get("/ModDate")),
                "encrypted": reader.is_encrypted,
            }
            # Drop empty/None fields to keep the output readable
            metadata["pdf"] = {k: v for k, v in pdf_meta.items() if v not in (None, "")}
        except Exception as exc:  # pragma: no cover - runtime dependency may be absent
            metadata["error"] = str(exc)

    # ------------------------------------------------------------------
    # DOCX
    # ------------------------------------------------------------------
    def _parse_docx(self, file_path: str, metadata: dict) -> None:
        if DocxDocument is None:
            metadata["note"] = "python-docx n'est pas installé : impossible d'analyser ce fichier."
            return

        try:
            document = DocxDocument(file_path)
            props = document.core_properties
            docx_meta = {
                "paragraphs": len(document.paragraphs),
                "title": self._clean_value(props.title),
                "author": self._clean_value(props.author),
                "last_modified_by": self._clean_value(props.last_modified_by),
                "subject": self._clean_value(props.subject),
                "keywords": self._clean_value(props.keywords),
                "comments": self._clean_value(props.comments),
                "category": self._clean_value(props.category),
                "language": self._clean_value(props.language),
                "revision": self._clean_value(props.revision),
                "created": self._clean_value(props.created),
                "modified": self._clean_value(props.modified),
                "last_printed": self._clean_value(props.last_printed),
            }
            metadata["docx"] = {k: v for k, v in docx_meta.items() if v not in (None, "")}
        except Exception as exc:  # pragma: no cover - runtime dependency may be absent
            metadata["error"] = str(exc)

    # ------------------------------------------------------------------
    # ODT (OpenDocument Text) — not handled by python-docx/pypdf, so we
    # read META-INF/meta.xml ourselves. ODT files are just ZIP archives.
    # ------------------------------------------------------------------
    def _parse_odt(self, file_path: str, metadata: dict) -> None:
        try:
            with zipfile.ZipFile(file_path) as archive:
                if "meta.xml" not in archive.namelist():
                    metadata["note"] = "Aucune métadonnée trouvée dans ce fichier .odt (meta.xml manquant)."
                    return
                with archive.open("meta.xml") as meta_file:
                    tree = ET.parse(meta_file)

            root = tree.getroot()
            meta_el = root.find("office:meta", _ODF_NAMESPACES)
            if meta_el is None:
                metadata["note"] = "Section de métadonnées vide dans ce fichier .odt."
                return

            def text_of(tag_ns: str) -> str | None:
                el = meta_el.find(tag_ns, _ODF_NAMESPACES)
                return el.text if el is not None else None

            odt_meta = {
                "title": text_of("dc:title"),
                "author": text_of("dc:creator") or text_of("meta:initial-creator"),
                "initial_creator": text_of("meta:initial-creator"),
                "subject": text_of("dc:subject"),
                "keywords": text_of("meta:keyword"),
                "description": text_of("dc:description"),
                "created": text_of("meta:creation-date"),
                "modified": text_of("dc:date"),
                "generator": text_of("meta:generator"),
                "editing_cycles": text_of("meta:editing-cycles"),
            }
            metadata["odt"] = {k: v for k, v in odt_meta.items() if v not in (None, "")}
        except Exception as exc:
            metadata["error"] = str(exc)

    # ------------------------------------------------------------------
    # TXT
    # ------------------------------------------------------------------
    def _parse_txt(self, path: Path, metadata: dict) -> None:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            metadata["text"] = content[:500]
            metadata["text_stats"] = {
                "characters": len(content),
                "lines": content.count("\n") + 1 if content else 0,
                "words": len(content.split()),
                "truncated": len(content) > 500,
            }
        except Exception as exc:  # pragma: no cover - runtime dependency may be absent
            metadata["error"] = str(exc)

    # ------------------------------------------------------------------
    # Shared helper
    # ------------------------------------------------------------------
    def _clean_value(self, value):
        """Make metadata values JSON/display friendly.

        pypdf can return its own string-like wrapper types (and sometimes
        already-parsed datetimes for /CreationDate on newer versions);
        python-docx's core_properties.created/modified are always plain
        datetime.datetime objects. None of these are JSON-serializable
        as-is, so this is the same fix applied to image_parser.py earlier.
        """
        if value is None:
            return None

        if isinstance(value, (datetime, date)):
            try:
                return value.isoformat()
            except Exception:
                return str(value)

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="replace").strip("\x00")
            except Exception:
                return value.hex()

        if isinstance(value, (list, tuple)):
            return [self._clean_value(item) for item in value]

        # Fallback for pypdf's internal types (e.g. IndirectObject, TextStringObject)
        try:
            return str(value)
        except Exception:
            return None
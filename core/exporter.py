import csv
import json
from pathlib import Path


class Exporter:
    """Handles export of extracted metadata."""

    def export(self, records: list[dict], output_path: str, fmt: str = "json") -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fmt = fmt.lower()

        if fmt == "json":
            output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
            return str(output)

        if fmt == "csv":
            with output.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["file", "type", "metadata", "sensitive_fields"])
                writer.writeheader()
                for record in records:
                    writer.writerow(
                        {
                            "file": record.get("file", ""),
                            "type": record.get("type", ""),
                            "metadata": json.dumps(record.get("metadata", {}), ensure_ascii=False),
                            "sensitive_fields": ", ".join(record.get("sensitive_fields", [])),
                        }
                    )
            return str(output)

        if fmt == "pdf":
            self._write_pdf(output, records)
            return str(output)

        raise ValueError(f"Format non pris en charge: {fmt}")

    def _write_pdf(self, output_path: Path, records: list[dict]) -> None:
        lines = ["KeroScope export", ""]
        for record in records:
            lines.append(record.get("file", ""))
            lines.append(f"Type: {record.get('type', 'unknown')}")
            lines.append(f"Sensitive fields: {', '.join(record.get('sensitive_fields', [])) or 'none'}")
            lines.append("")

        text = "\n".join(lines)
        escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 11 Tf 50 770 Td ({escaped_text}) Tj ET"
        content_bytes = stream.encode("latin-1", errors="ignore")

        objects = []
        objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
        objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
        objects.append(b"4 0 obj\n<< /Length 0 >>\nstream\n\nendstream\nendobj\n")
        objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

        # Replace the content stream with actual text data.
        content_obj = f"4 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n".encode("ascii") + content_bytes + b"\nendstream\nendobj\n"
        objects[3] = content_obj

        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(len(pdf))
            pdf.extend(obj)

        startxref = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode("ascii"))
        output_path.write_bytes(pdf)

import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk


class MetadataView(tk.Frame):
    """Widget for displaying metadata content."""

    def __init__(self, master=None) -> None:
        super().__init__(master, bg="#07090f")
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        label = ttk.Label(self, text="Métadonnées", background="#07090f", foreground="#f8fafc")
        label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.text = tk.Text(
            self,
            wrap="word",
            bg="#111827",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            highlightthickness=0,
            bd=0,
        )
        self.text.grid(row=1, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

    def display_records(self, records: list[dict]) -> None:
        self.text.delete("1.0", tk.END)
        if not records:
            self.text.insert(tk.END, "Aucune métadonnée à afficher")
            return

        for record in records:
            file_name = Path(record.get("file", "")).name
            self.text.insert(tk.END, f"Fichier: {file_name}\n")
            self.text.insert(tk.END, f"Type: {record.get('type', 'unknown')}\n")
            metadata = record.get("metadata", {})
            try:
                metadata_text = json.dumps(metadata, indent=2, ensure_ascii=False, default=str)
            except Exception as exc:
                metadata_text = f"[Erreur d'affichage des métadonnées: {exc}]"
            self.text.insert(tk.END, metadata_text)
            if record.get("sensitive_fields"):
                self.text.insert(tk.END, "\n\nChamps sensibles:\n")
                self.text.insert(tk.END, "\n".join(record["sensitive_fields"]))
            self.text.insert(tk.END, "\n\n" + "-" * 60 + "\n")
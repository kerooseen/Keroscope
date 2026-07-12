import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:
    Image = None
    ImageOps = None
    ImageTk = None


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

from core.exporter import Exporter
from core.extractor import Extractor
from ui.file_list_widget import FileListWidget
from ui.metadata_view import MetadataView


class MainWindow:
    """Main application window for KeroScope."""

    def __init__(self) -> None:
        self.root = self._create_root_window()
        self.root.title("KeroScope")
        self.root.geometry("1180x740")
        self.root.minsize(980, 650)
        self._set_window_icon()
        self._apply_dark_theme()
        self.extractor = Extractor()
        self.exporter = Exporter()
        self.records: list[dict] = []
        self.status_var = tk.StringVar(value="Prêt à analyser vos fichiers")
        self.count_var = tk.StringVar(value="0 fichier(s)")
        self.sensitive_var = tk.StringVar(value="0 champ sensible")
        self.type_var = tk.StringVar(value="Aucun type")
        self.animation_phase = 0
        self._build_ui()
        self.root.bind("<Configure>", self._on_root_configure)
        self._bind_drop_target()
        self._bind_fallback_drag_drop()

    def _create_root_window(self):
        self.dnd_files = None
        try:
            return tk.Tk()
        except Exception:
            return tk.Tk()

    def _set_window_icon(self) -> None:
        logo_path = ASSETS_DIR / "logo.ico"
        if logo_path.exists():
            try:
                self.root.iconbitmap(str(logo_path))
            except Exception:
                pass

    def _load_image(self, path: Path, size: tuple[int, int]):
        """Load an image and fit it exactly to `size` (crop-to-fill, no distortion)."""
        if not path.exists():
            return None

        try:
            if Image is not None and ImageTk is not None:
                image = Image.open(path).convert("RGBA")
                resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                if ImageOps is not None:
                    fitted = ImageOps.fit(image, size, method=resample, centering=(0.5, 0.5))
                else:
                    fitted = image.resize(size, resample)
                return ImageTk.PhotoImage(fitted)
        except Exception:
            pass

        try:
            return tk.PhotoImage(file=str(path))
        except Exception:
            return None

    def _apply_dark_theme(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background="#06070b")
        style.configure("Card.TFrame", background="#090b10")
        style.configure("TLabel", background="#06070b", foreground="#f8fafc")
        style.configure("Header.TLabel", background="#06070b", foreground="#f8fafc", font=("Segoe UI", 18, "bold"))
        style.configure("Subtle.TLabel", background="#06070b", foreground="#7b879c")
        style.configure("Accent.TButton", background="#6d28d9", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#7c3aed"), ("!disabled", "#6d28d9")], foreground=[("active", "#ffffff"), ("!disabled", "#ffffff")])
        style.configure("Secondary.TButton", background="#121723", foreground="#e5e7eb")
        style.map("Secondary.TButton", background=[("active", "#1b2230"), ("!disabled", "#121723")], foreground=[("active", "#f8fafc"), ("!disabled", "#f8fafc")])
        self.root.configure(bg="#020202")

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)

        self.background_canvas = tk.Canvas(self.root, bg="#020202", highlightthickness=0)
        self.background_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        header = tk.Frame(self.root, bg="#06070b", bd=1, relief="solid", highlightthickness=1, highlightbackground="#2b2f3a", highlightcolor="#7c3aed")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)

        header.columnconfigure(1, weight=1)
        header.columnconfigure(3, weight=0)

        logo_wrapper = tk.Frame(header, bg="#090b10", bd=1, relief="solid", highlightthickness=1, highlightbackground="#7c3aed")
        logo_wrapper.grid(row=0, column=0, rowspan=2, sticky="w", padx=(10, 12), pady=(8, 8))
        self.logo_image = self._load_image(ASSETS_DIR / "logo.png", (48, 48))
        if self.logo_image is not None:
            self.logo_label = ttk.Label(logo_wrapper, image=self.logo_image, background="#090b10")
            self.logo_label.image = self.logo_image
            self.logo_label.pack(padx=4, pady=4)
        else:
            self.logo_label = ttk.Label(logo_wrapper, text="K", foreground="#ffffff", background="#6d28d9", font=("Segoe UI", 20, "bold"))
            self.logo_label.pack(padx=4, pady=4)

        ttk.Label(header, text="KeroScope", style="Header.TLabel").grid(row=0, column=1, sticky="w")
        ttk.Label(header, text="Analyseur de métadonnées multi-formats, developper par Keroseen, discord: 4rvv_", style="Subtle.TLabel").grid(row=1, column=1, sticky="w", pady=(2, 0))

        profile_frame = tk.Frame(header, bg="#06070b")
        profile_frame.grid(row=0, column=2, rowspan=2, sticky="e", padx=(20, 12), pady=(6, 6))
        self.profile_image = self._load_image(ASSETS_DIR / "ProfilePicture.jpg", (28, 28))
        if self.profile_image is not None:
            profile_label = ttk.Label(profile_frame, image=self.profile_image, background="#06070b")
            profile_label.image = self.profile_image
            profile_label.pack(side="left")
        else:
            ttk.Label(profile_frame, text="P", foreground="#ffffff", background="#8b5cf6", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(profile_frame, text="Keroseen", foreground="#c084fc", font=("Segoe UI", 10, "bold"), background="#06070b").pack(side="left", padx=(6, 0))

        toolbar = tk.Frame(self.root, bg="#020202", bd=0, highlightthickness=0)
        toolbar.grid(row=1, column=0, sticky="ew")

        ttk.Button(toolbar, text="Importer des fichiers", style="Accent.TButton", command=self._import_files).pack(side="left")
        ttk.Button(toolbar, text="Importer un dossier", style="Secondary.TButton", command=self._import_folder).pack(side="left", padx=(10, 0))
        ttk.Button(toolbar, text="Tout nettoyer", style="Secondary.TButton", command=self._clear_all).pack(side="left", padx=(10, 0))
        ttk.Button(toolbar, text="Exporter JSON", style="Secondary.TButton", command=lambda: self._export_data("json")).pack(side="left", padx=(10, 0))
        ttk.Button(toolbar, text="Exporter CSV", style="Secondary.TButton", command=lambda: self._export_data("csv")).pack(side="left", padx=(10, 0))
        ttk.Button(toolbar, text="Exporter PDF", style="Secondary.TButton", command=lambda: self._export_data("pdf")).pack(side="left", padx=(10, 0))
        ttk.Button(toolbar, text="Nettoyer infos sensibles", style="Secondary.TButton", command=self._clean_sensitive_metadata).pack(side="left", padx=(10, 0))

        summary = tk.Frame(self.root, bg="#07090f", bd=1, relief="solid", highlightthickness=1, highlightbackground="#232631", highlightcolor="#6d28d9")
        summary.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        summary.columnconfigure(0, weight=1)
        summary.columnconfigure(1, weight=1)
        summary.columnconfigure(2, weight=1)

        self._create_summary_card(summary, 0, "Fichiers", self.count_var)
        self._create_summary_card(summary, 1, "Champs sensibles", self.sensitive_var)
        self._create_summary_card(summary, 2, "Type courant", self.type_var)

        content = tk.Frame(self.root, bg="#07090f", bd=0, relief="flat", highlightthickness=0)
        content.grid(row=3, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=2)
        content.rowconfigure(0, weight=1)

        self.file_list = FileListWidget(content, on_select=self._show_selected_metadata)
        self.file_list.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.metadata_view = MetadataView(content)
        self.metadata_view.grid(row=0, column=1, sticky="nsew")

        ttk.Label(
            content,
            text="Glissez-déposez des fichiers ici ou utilisez le bouton d’import.",
            style="Subtle.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.status_label = ttk.Label(self.root, textvariable=self.status_var, style="Subtle.TLabel")
        self.status_label.grid(row=4, column=0, sticky="w", pady=(8, 0))

        self.copyright_label = ttk.Label(
            self.root,
            text="© 2026 KeroScope",
            foreground="#5b6472",
            font=("Segoe UI", 8),
        )
        self.copyright_label.place(x=10, y=10)
        self._start_animation()
        self._draw_background_gradient()
        self._position_copyright()

        self.drop_overlay = tk.Label(
            content,
            text="",
            bg="#07090f",
            fg="#8b5cf6",
            font=("Segoe UI", 11, "bold"),
            bd=0,
        )
        self.drop_overlay.place_forget()

    def _create_summary_card(self, parent, column, title, variable) -> None:
        card = tk.Frame(parent, bg="#0b0e14", bd=1, relief="solid", highlightthickness=1, highlightbackground="#2b2f3a", highlightcolor="#7c3aed")
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0))
        ttk.Label(card, text=title, style="Subtle.TLabel").pack(anchor="w", pady=(6, 0))
        ttk.Label(card, textvariable=variable, foreground="#f8fafc", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 6))

    def _bind_drop_target(self) -> None:
        if self.dnd_files is None:
            return
        self.root.drop_target_register(self.dnd_files)
        self.root.dnd_bind("<<Drop>>", self._on_drop)

    def _bind_fallback_drag_drop(self) -> None:
        return

    def _show_drop_overlay(self, _event=None) -> None:
        return

    def _hide_drop_overlay(self, _event=None) -> None:
        return

    def _import_files(self) -> None:
        files = filedialog.askopenfilenames(title="Sélectionner des fichiers")
        if files:
            self._process_files(list(files))

    def _import_folder(self) -> None:
        folder = filedialog.askdirectory(title="Sélectionner un dossier")
        if not folder:
            return
        files = self._collect_files_from_folder(folder)
        if files:
            self._process_files(files)
        else:
            self.status_var.set("Aucun fichier trouvé dans ce dossier.")

    def _clear_all(self) -> None:
        self.file_list.clear()
        self.records = []
        self.metadata_view.display_records([])
        self._update_summary()
        self.status_var.set("Liste nettoyée.")

    def _collect_files_from_folder(self, folder: str) -> list[str]:
        folder_path = Path(folder)
        if not folder_path.exists():
            return []
        supported_extensions = {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",
            ".pdf", ".doc", ".docx", ".txt", ".odt",
            ".mp3", ".wav", ".ogg", ".flac",
            ".mp4", ".avi", ".mov", ".mkv",
            ".zip", ".rar", ".7z", ".tar", ".gz"
        }
        files: list[str] = []
        for path in folder_path.rglob("*"):
            if path.is_file() and path.suffix.lower() in supported_extensions:
                files.append(str(path))
        return sorted(files)

    def _on_drop(self, event) -> None:
        if not event.data:
            return
        files = self.root.tk.splitlist(event.data)
        self._process_files(files)

    def _process_files(self, paths: list[str]) -> None:
        unique_paths = [path for path in paths if Path(path).exists()]
        if not unique_paths:
            self.status_var.set("Aucun fichier valide trouvé.")
            return
        self.file_list.add_files(unique_paths)
        self.records = [self.extractor.extract(path) for path in unique_paths]
        self.metadata_view.display_records(self.records)
        self._update_summary()
        if self.records:
            self.file_list.select_path(unique_paths[0])
            self._show_selected_metadata(unique_paths[0])
        self.status_var.set(f"{len(self.records)} fichier(s) analysé(s) — prêt pour l’export.")

    def _show_selected_metadata(self, file_path: str | None) -> None:
        if not file_path:
            return
        matching = [record for record in self.records if record.get("file") == file_path]
        if matching:
            self.metadata_view.display_records(matching)
            self.type_var.set(matching[0].get("type", "unknown"))

    def _export_data(self, fmt: str) -> None:
        if not self.records:
            self.status_var.set("Aucun résultat à exporter.")
            return
        output_path = filedialog.asksaveasfilename(
            title=f"Exporter vers {fmt.upper()}",
            defaultextension=fmt,
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("Tous les fichiers", "*.*")],
        )
        if output_path:
            self.exporter.export(self.records, output_path, fmt)
            self.status_var.set(f"Export {fmt.upper()} terminé.")

    def _clean_sensitive_metadata(self) -> None:
        if not self.records:
            self.status_var.set("Aucun résultat à nettoyer.")
            return
        cleaned_records = [self.extractor.clean_sensitive_metadata(record) for record in self.records]
        self.records = cleaned_records
        self.metadata_view.display_records(cleaned_records)
        self._update_summary()
        self.status_var.set("Métadonnées sensibles nettoyées.")

    def _on_root_configure(self, event) -> None:
        self.root.after(30, self._draw_background_gradient)
        self.root.after(30, self._position_copyright)

    def _position_copyright(self) -> None:
        if not hasattr(self, "copyright_label"):
            return
        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            self.copyright_label.place(x=max(10, width - 120), y=max(12, height - 26))
        except Exception:
            pass

    def _draw_background_gradient(self) -> None:
        width = max(1, self.root.winfo_width())
        height = max(1, self.root.winfo_height())
        if width <= 1 or height <= 1:
            self.root.after(50, self._draw_background_gradient)
            return
        self.background_canvas.delete("all")
        steps = max(14, height // 35)
        for i in range(steps):
            y0 = int(i * height / steps)
            y1 = int((i + 1) * height / steps)
            ratio = i / max(1, steps - 1)
            base = self._blend_colors("#020202", "#05070b", ratio)
            accent = self._blend_colors("#05070b", "#16131d", min(1.0, ratio * 0.9))
            color = self._blend_colors(base, accent, 0.2)
            self.background_canvas.create_rectangle(0, y0, width, y1, fill=color, outline=color)

        self.background_canvas.create_oval(-220, -220, width // 2 + 120, height // 3 + 100, fill="#1a1026", outline="")
        self.background_canvas.create_oval(width // 2 - 80, height // 3 - 40, width + 220, height + 100, fill="#0c0f16", outline="")
        self.background_canvas.create_rectangle(0, 0, width, height, fill="", outline="")
        self.background_canvas.configure(width=width, height=height)

    def _blend_colors(self, color1: str, color2: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _start_animation(self) -> None:
        if not hasattr(self, "logo_canvas") or not hasattr(self, "status_label"):
            return
        self.animation_phase = (self.animation_phase + 1) % 360
        color = f"#{self._hsv_to_hex(self.animation_phase, 0.55, 0.95)}"
        try:
            self.logo_canvas.itemconfig(1, outline=color)
            self.logo_canvas.itemconfig(2, fill=color)
        except Exception:
            pass
        self.status_label.configure(foreground="#cbd5e1")
        self.root.after(50, self._start_animation)

    def _hsv_to_hex(self, h, s, v):
        h %= 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c
        if 0 <= h < 60:
            r1, g1, b1 = c, x, 0
        elif 60 <= h < 120:
            r1, g1, b1 = x, c, 0
        elif 120 <= h < 180:
            r1, g1, b1 = 0, c, x
        elif 180 <= h < 240:
            r1, g1, b1 = 0, x, c
        elif 240 <= h < 300:
            r1, g1, b1 = x, 0, c
        else:
            r1, g1, b1 = c, 0, x
        r = int((r1 + m) * 255)
        g = int((g1 + m) * 255)
        b = int((b1 + m) * 255)
        return f"{r:02x}{g:02x}{b:02x}"

    def _update_summary(self) -> None:
        self.count_var.set(f"{len(self.records)} fichier(s)")
        sensitive_count = sum(len(record.get("sensitive_fields", [])) for record in self.records)
        self.sensitive_var.set(f"{sensitive_count} champ(s) sensible(s)")
        if self.records:
            self.type_var.set(self.records[-1].get("type", "unknown"))
        else:
            self.type_var.set("Aucun type")

    def run(self) -> None:
        self.root.mainloop()
import tkinter as tk
from tkinter import ttk


class FileListWidget(tk.Frame):
    """Widget displaying imported files."""

    def __init__(self, master=None, on_select=None) -> None:
        super().__init__(master, bg="#07090f")
        self.on_select = on_select
        self._build_ui()
        self.files = []

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        label = ttk.Label(self, text="Fichiers importés", background="#07090f", foreground="#f8fafc")
        label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._on_scrollbar)
        self.listbox = tk.Listbox(
            self,
            height=20,
            bg="#111827",
            fg="#f8fafc",
            selectbackground="#4f46e5",
            selectforeground="#ffffff",
            highlightthickness=0,
            bd=0,
            exportselection=False,
            yscrollcommand=scrollbar.set,
        )
        self.listbox.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.listbox.bind("<<ListboxSelect>>", self._on_selection)
        self.listbox.bind("<Double-Button-1>", self._on_selection)
        self.listbox.bind("<Return>", self._on_selection)

    def add_files(self, paths: list[str]) -> None:
        for path in paths:
            if path not in self.files:
                self.files.append(path)
                self.listbox.insert(tk.END, path)

    def clear(self) -> None:
        self.files.clear()
        self.listbox.delete(0, tk.END)

    def remove_path(self, path: str) -> None:
        if path not in self.files:
            return
        index = self.files.index(path)
        self.files.pop(index)
        self.listbox.delete(index)

    def get_selected_path(self) -> str | None:
        selection = self.listbox.curselection()
        if not selection:
            return None
        return self.listbox.get(selection[0])

    def select_path(self, path: str) -> None:
        if path in self.files:
            index = self.files.index(path)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(index)
            self.listbox.activate(index)
            self.listbox.see(index)

    def _on_selection(self, _event) -> None:
        if self.on_select:
            self.on_select(self.get_selected_path())

    def _on_scrollbar(self, *_args) -> None:
        self.listbox.yview(*_args)

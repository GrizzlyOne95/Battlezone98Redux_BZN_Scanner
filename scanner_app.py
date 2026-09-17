import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from bzn_scan import BZNParser, STOCK_SET
from odf_evidence import resolve_evidence
from odf_validator import validate_directory, validate_zip


APP_USER_MODEL_ID = "GrizzlyOne95.Battlezone98Redux.BZNScanner"


def _set_app_user_model_id():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def _resolve_bundled_icon(name):
    """Locate a bundled icon working from source and under sys._MEIPASS."""
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "branding", name))
        candidates.append(os.path.join(meipass, name))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "branding", name))
    candidates.append(os.path.join(here, name))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def apply_window_icon(window):
    """Apply the canonical (BZNTools) app icon to a Tk/Toplevel window."""
    try:
        ico_path = _resolve_bundled_icon("app_icon.ico")
        if ico_path:
            try:
                window.iconbitmap(ico_path)
            except Exception:
                pass
        png_path = _resolve_bundled_icon("app_icon.png")
        if png_path:
            try:
                image = tk.PhotoImage(file=png_path)
                window.iconphoto(True, image)
                window._battlezone_app_icon = image
            except Exception:
                pass
    except Exception:
        pass


_set_app_user_model_id()


SEVERITY_ORDER = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}


class BZNScannerApp:
    def __init__(self, root):
        self.root = root
        apply_window_icon(self.root)
        self.root.title("BZ98R Mission Scanner")
        self.root.geometry("1280x760")

        self.current_file = None
        self.source_kind = None  # bzn | folder | zip
        self.source_path = None
        self.dependency_data = []
        self.issue_data = []
        self.issue_lookup = {}

        controls = tk.Frame(root)
        controls.pack(pady=(10, 4), padx=10, fill=tk.X)

        tk.Button(controls, text="Load BZN", command=self.load_file).pack(side=tk.LEFT)
        tk.Button(controls, text="Scan ODF Folder", command=self.load_folder).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(controls, text="Scan ZIP", command=self.load_zip).pack(side=tk.LEFT, padx=(8, 0))

        self.custom_only = tk.BooleanVar(value=False)
        tk.Checkbutton(
            controls,
            text="Custom ODFs Only",
            variable=self.custom_only,
            command=self.refresh_dependencies,
        ).pack(side=tk.LEFT, padx=(18, 0))

        self.referenced_only = tk.BooleanVar(value=False)
        self.referenced_check = tk.Checkbutton(
            controls,
            text="Validate Referenced ODFs Only",
            variable=self.referenced_only,
            command=self.revalidate,
        )
        self.referenced_check.pack(side=tk.LEFT, padx=(12, 0))
        self.referenced_check.configure(state=tk.DISABLED)

        self.status_lbl = tk.Label(root, text="Load a BZN, ODF folder, or ZIP to begin", fg="gray", anchor="w")
        self.status_lbl.pack(padx=10, fill=tk.X)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.dependencies_tab = ttk.Frame(self.notebook)
        self.validation_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.dependencies_tab, text="BZN Dependencies")
        self.notebook.add(self.validation_tab, text="ODF Validation")

        self._build_dependency_tab()
        self._build_validation_tab()

    def _build_dependency_tab(self):
        columns = ("status", "type", "filename")
        self.dep_tree = ttk.Treeview(self.dependencies_tab, columns=columns, show="headings")
        self.dep_tree.heading("status", text="Status", command=lambda: self.sort_dependency_column("status", False))
        self.dep_tree.heading("type", text="Type", command=lambda: self.sort_dependency_column("type", False))
        self.dep_tree.heading("filename", text="Filename", command=lambda: self.sort_dependency_column("filename", False))
        self.dep_tree.column("status", width=110, stretch=False)
        self.dep_tree.column("type", width=110, stretch=False)
        self.dep_tree.column("filename", width=900)
        self.dep_tree.tag_configure("missing", foreground="red")
        self.dep_tree.tag_configure("stock", foreground="gray")
        self.dep_tree.pack(fill=tk.BOTH, expand=True)

    def _build_validation_tab(self):
        columns = ("severity", "filename", "line", "location", "message", "suggestion")
        self.issue_tree = ttk.Treeview(self.validation_tab, columns=columns, show="headings")
        self.issue_tree.heading("severity", text="Severity", command=lambda: self.sort_issue_column("severity", False))
        self.issue_tree.heading("filename", text="File", command=lambda: self.sort_issue_column("filename", False))
        self.issue_tree.heading("line", text="Line")
        self.issue_tree.heading("location", text="Section / Key")
        self.issue_tree.heading("message", text="Finding")
        self.issue_tree.heading("suggestion", text="Suggested Fix")
        self.issue_tree.column("severity", width=90, stretch=False)
        self.issue_tree.column("filename", width=145, stretch=False)
        self.issue_tree.column("line", width=55, stretch=False, anchor=tk.CENTER)
        self.issue_tree.column("location", width=180, stretch=False)
        self.issue_tree.column("message", width=455)
        self.issue_tree.column("suggestion", width=300)
        self.issue_tree.tag_configure("critical", foreground="#b00020")
        self.issue_tree.tag_configure("error", foreground="red")
        self.issue_tree.tag_configure("warning", foreground="#9a6700")
        self.issue_tree.pack(fill=tk.BOTH, expand=True)
        self.issue_tree.bind("<Double-1>", self.show_issue_details)

        hint = tk.Label(
            self.validation_tab,
            text=(
                "Double-click a finding for rule/evidence details. Validation is read-only; "
                "files are never modified. Folder and ZIP scans do not require a BZN."
            ),
            fg="gray",
            anchor="w",
        )
        hint.pack(fill=tk.X, pady=(4, 0))

    def _reset_source(self, kind, path):
        self.source_kind = kind
        self.source_path = path
        self.current_file = path if kind == "bzn" else None
        self.dependency_data = []
        self.issue_data = []
        self.referenced_only.set(False)
        self.referenced_check.configure(state=tk.NORMAL if kind == "bzn" else tk.DISABLED)
        self.refresh_dependencies()
        self.refresh_issues()

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("BZN Files", "*.bzn"), ("All Files", "*.*")])
        if not path:
            return
        self._reset_source("bzn", path)
        self.analyze_bzn()

    def load_folder(self):
        path = filedialog.askdirectory(title="Select folder containing ODF files")
        if not path:
            return
        self._reset_source("folder", path)
        self.issue_data = validate_directory(path, known_odfs=STOCK_SET)
        self.refresh_issues()
        self._update_status()
        self.notebook.select(self.validation_tab)

    def load_zip(self):
        path = filedialog.askopenfilename(filetypes=[("ZIP archives", "*.zip"), ("All Files", "*.*")])
        if not path:
            return
        self._reset_source("zip", path)
        self.issue_data = validate_zip(path, known_odfs=STOCK_SET)
        self.refresh_issues()
        self._update_status()
        self.notebook.select(self.validation_tab)

    def analyze_bzn(self):
        if not self.current_file:
            return

        directory = os.path.dirname(self.current_file)
        try:
            matches = BZNParser(self.current_file).parse()
            self.dependency_data = []
            for odf_base in matches:
                filename = f"{odf_base}.odf"
                is_stock = filename.lower() in STOCK_SET
                exists = self._case_insensitive_exists(directory, filename)
                status = "OK" if exists or is_stock else "MISSING"
                odf_type = "Stock" if is_stock else "Custom"
                self.dependency_data.append((status, odf_type, filename))

            self.dependency_data.sort(key=lambda row: (row[1], row[2].lower()))
            self.refresh_dependencies()
            self._run_odf_validation(directory)
            self._update_status()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def revalidate(self):
        if not self.source_kind or not self.source_path:
            return
        try:
            if self.source_kind == "zip":
                self.issue_data = validate_zip(self.source_path, known_odfs=STOCK_SET)
            elif self.source_kind == "folder":
                self.issue_data = validate_directory(self.source_path, known_odfs=STOCK_SET)
            elif self.source_kind == "bzn":
                self._run_odf_validation(os.path.dirname(self.source_path))
            self.refresh_issues()
            self._update_status()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _run_odf_validation(self, directory):
        filenames = None
        if self.referenced_only.get():
            filenames = [row[2] for row in self.dependency_data if row[1] == "Custom"]
        self.issue_data = validate_directory(directory, filenames=filenames, known_odfs=STOCK_SET)
        self.refresh_issues()

    @staticmethod
    def _case_insensitive_exists(directory, filename):
        target = filename.lower()
        try:
            return any(entry.name.lower() == target for entry in os.scandir(directory) if entry.is_file())
        except OSError:
            return False

    def _update_status(self):
        critical = sum(1 for issue in self.issue_data if issue.severity == "CRITICAL")
        errors = sum(1 for issue in self.issue_data if issue.severity == "ERROR")
        warnings = sum(1 for issue in self.issue_data if issue.severity == "WARNING")

        if self.source_kind == "bzn":
            filename = os.path.basename(self.source_path)
            custom_missing = sum(1 for row in self.dependency_data if row[0] == "MISSING" and row[1] == "Custom")
            prefix = (
                f"{filename}  |  {len(self.dependency_data)} BZN ODF references  |  "
                f"{custom_missing} missing custom"
            )
        elif self.source_kind == "folder":
            root = Path(self.source_path)
            try:
                odf_count = sum(1 for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".odf")
            except OSError:
                odf_count = 0
            prefix = f"Folder: {root.name or root}  |  {odf_count} ODF files"
        elif self.source_kind == "zip":
            prefix = f"ZIP: {os.path.basename(self.source_path)}"
        else:
            prefix = "No source loaded"

        self.status_lbl.config(
            text=f"{prefix}  |  ODF: {critical} critical, {errors} errors, {warnings} warnings",
            fg="#b00020" if critical else ("red" if errors else "black"),
        )

    def refresh_dependencies(self):
        for item in self.dep_tree.get_children():
            self.dep_tree.delete(item)

        data = self.dependency_data
        if self.custom_only.get():
            data = [row for row in data if row[1] == "Custom"]

        for row in data:
            tags = ()
            if row[0] == "MISSING":
                tags = ("missing",)
            elif row[1] == "Stock":
                tags = ("stock",)
            self.dep_tree.insert("", tk.END, values=row, tags=tags)

    def refresh_issues(self):
        for item in self.issue_tree.get_children():
            self.issue_tree.delete(item)
        self.issue_lookup = {}

        for issue in self.issue_data:
            location = issue.section
            if issue.key:
                location = f"{location} / {issue.key}" if location else issue.key
            tag = issue.severity.lower()
            iid = self.issue_tree.insert(
                "",
                tk.END,
                values=(
                    issue.severity,
                    issue.filename,
                    issue.line or "",
                    location,
                    issue.message,
                    issue.suggestion,
                ),
                tags=(tag,),
            )
            self.issue_lookup[iid] = issue

    def show_issue_details(self, _event=None):
        selection = self.issue_tree.selection()
        if not selection:
            return
        issue = self.issue_lookup.get(selection[0])
        if issue is None:
            return

        location = issue.section
        if issue.key:
            location = f"{location} / {issue.key}" if location else issue.key
        if issue.line:
            location += f" (line {issue.line})"

        detail = f"{issue.severity}: {issue.filename}\n{location}\n\n{issue.message}"
        if issue.suggestion:
            detail += f"\n\nSuggested fix:\n{issue.suggestion}"
        if issue.rule_id:
            detail += f"\n\nRule:\n{issue.rule_id}"

        evidence = resolve_evidence(issue.evidence_ids)
        if evidence:
            detail += "\n\nStructured evidence:"
            for item in evidence:
                detail += f"\n\n{item.evidence_id}\n{item.summary()}"
        elif issue.source:
            detail += f"\n\nEvidence / rule source:\n{issue.source}"

        messagebox.showinfo("ODF Validation Finding", detail)

    def sort_dependency_column(self, column, reverse):
        index = {"status": 0, "type": 1, "filename": 2}[column]
        self.dependency_data.sort(key=lambda row: row[index].lower(), reverse=reverse)
        self.refresh_dependencies()
        self.dep_tree.heading(column, command=lambda: self.sort_dependency_column(column, not reverse))

    def sort_issue_column(self, column, reverse):
        if column == "severity":
            self.issue_data.sort(key=lambda x: SEVERITY_ORDER.get(x.severity, 99), reverse=reverse)
        elif column == "filename":
            self.issue_data.sort(key=lambda x: x.filename.lower(), reverse=reverse)
        self.refresh_issues()
        self.issue_tree.heading(column, command=lambda: self.sort_issue_column(column, not reverse))


if __name__ == "__main__":
    root = tk.Tk()
    BZNScannerApp(root)
    root.mainloop()

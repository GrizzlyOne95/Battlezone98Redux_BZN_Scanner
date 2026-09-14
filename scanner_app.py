import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from bzn_scan import BZNParser, STOCK_SET
from odf_validator import validate_directory


SEVERITY_ORDER = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}


class BZNScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BZ98R BZN Scanner")
        self.root.geometry("1180x720")
        self.current_file = None
        self.dependency_data = []
        self.issue_data = []

        controls = tk.Frame(root)
        controls.pack(pady=(10, 4), padx=10, fill=tk.X)

        tk.Button(controls, text="Load BZN", command=self.load_file).pack(side=tk.LEFT)

        self.custom_only = tk.BooleanVar(value=False)
        tk.Checkbutton(
            controls,
            text="Custom ODFs Only",
            variable=self.custom_only,
            command=self.refresh_dependencies,
        ).pack(side=tk.LEFT, padx=(12, 0))

        self.referenced_only = tk.BooleanVar(value=False)
        tk.Checkbutton(
            controls,
            text="Validate Referenced ODFs Only",
            variable=self.referenced_only,
            command=self.revalidate,
        ).pack(side=tk.LEFT, padx=(12, 0))

        self.status_lbl = tk.Label(root, text="Select a BZN to begin", fg="gray", anchor="w")
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
        self.dep_tree.column("filename", width=850)
        self.dep_tree.tag_configure("missing", foreground="red")
        self.dep_tree.tag_configure("stock", foreground="gray")
        self.dep_tree.pack(fill=tk.BOTH, expand=True)

    def _build_validation_tab(self):
        columns = ("severity", "filename", "location", "message", "suggestion")
        self.issue_tree = ttk.Treeview(self.validation_tab, columns=columns, show="headings")
        self.issue_tree.heading("severity", text="Severity", command=lambda: self.sort_issue_column("severity", False))
        self.issue_tree.heading("filename", text="File", command=lambda: self.sort_issue_column("filename", False))
        self.issue_tree.heading("location", text="Section / Key")
        self.issue_tree.heading("message", text="Finding")
        self.issue_tree.heading("suggestion", text="Suggested Fix")
        self.issue_tree.column("severity", width=90, stretch=False)
        self.issue_tree.column("filename", width=150, stretch=False)
        self.issue_tree.column("location", width=190, stretch=False)
        self.issue_tree.column("message", width=430)
        self.issue_tree.column("suggestion", width=300)
        self.issue_tree.tag_configure("critical", foreground="#b00020")
        self.issue_tree.tag_configure("error", foreground="red")
        self.issue_tree.tag_configure("warning", foreground="#9a6700")
        self.issue_tree.pack(fill=tk.BOTH, expand=True)
        self.issue_tree.bind("<Double-1>", self.show_issue_details)

        hint = tk.Label(
            self.validation_tab,
            text="Double-click a finding for loader/source details. Validation is read-only; files are never modified.",
            fg="gray",
            anchor="w",
        )
        hint.pack(fill=tk.X, pady=(4, 0))

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("BZN Files", "*.bzn"), ("All Files", "*.*")])
        if path:
            self.current_file = path
            self.analyze()

    def analyze(self):
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
        if self.current_file:
            self._run_odf_validation(os.path.dirname(self.current_file))
            self._update_status()

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
        filename = os.path.basename(self.current_file) if self.current_file else ""
        custom_missing = sum(1 for row in self.dependency_data if row[0] == "MISSING" and row[1] == "Custom")
        critical = sum(1 for issue in self.issue_data if issue.severity == "CRITICAL")
        errors = sum(1 for issue in self.issue_data if issue.severity == "ERROR")
        warnings = sum(1 for issue in self.issue_data if issue.severity == "WARNING")
        self.status_lbl.config(
            text=(
                f"{filename}  |  {len(self.dependency_data)} BZN ODF references  |  "
                f"{custom_missing} missing custom  |  "
                f"ODF: {critical} critical, {errors} errors, {warnings} warnings"
            ),
            fg="black" if not critical else "#b00020",
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

        for issue in self.issue_data:
            location = issue.section
            if issue.key:
                location = f"{location} / {issue.key}" if location else issue.key
            tag = issue.severity.lower()
            self.issue_tree.insert(
                "",
                tk.END,
                values=(issue.severity, issue.filename, location, issue.message, issue.suggestion),
                tags=(tag,),
            )

    def show_issue_details(self, _event=None):
        selection = self.issue_tree.selection()
        if not selection:
            return
        item = selection[0]
        values = self.issue_tree.item(item, "values")
        if not values:
            return

        severity, filename, location, message, suggestion = values
        matching = next(
            (
                issue for issue in self.issue_data
                if issue.severity == severity
                and issue.filename == filename
                and ((f"{issue.section} / {issue.key}" if issue.key and issue.section else issue.section or issue.key) == location)
                and issue.message == message
            ),
            None,
        )
        source = matching.source if matching else ""
        detail = f"{severity}: {filename}\n{location}\n\n{message}"
        if suggestion:
            detail += f"\n\nSuggested fix:\n{suggestion}"
        if source:
            detail += f"\n\nEvidence / rule source:\n{source}"
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

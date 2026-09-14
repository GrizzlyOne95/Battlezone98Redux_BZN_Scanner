"""Battlezone 98 Redux ODF validation.

The validator is intentionally conservative: it reports loader mismatches and
known crash-risk omissions without rewriting user files. The rule data lives in
odf_schema.py so the checker can grow toward a codebase-derived schema instead
of accumulating one-off conditionals.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
import re
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple
import zipfile

from odf_schema import LOADER_RULES, REFERENCE_KEYS, LoaderRule


@dataclass(frozen=True)
class ODFIssue:
    severity: str
    filename: str
    section: str
    key: str
    message: str
    suggestion: str = ""
    source: str = ""
    rule_id: str = ""
    line: int = 0


@dataclass
class ODFDocument:
    path: Path
    sections: Dict[str, List[Tuple[str, str, int]]]
    original_sections: Dict[str, str]

    def has_section(self, name: str) -> bool:
        return name.lower() in self.sections

    def entries(self, section: str) -> List[Tuple[str, str, int]]:
        return list(self.sections.get(section.lower(), ()))

    def keys(self, section: str) -> Mapping[str, Tuple[str, int, str]]:
        out: Dict[str, Tuple[str, int, str]] = {}
        for key, value, line in self.sections.get(section.lower(), []):
            out[key.lower()] = (value, line, key)
        return out

    def value(self, section: str, key: str, default: str = "") -> str:
        return self.keys(section).get(key.lower(), (default, 0, key))[0]

    def class_label(self) -> str:
        for section in ("GameObjectClass", "GameObject", "OrdnanceClass", "WeaponClass"):
            value = self.value(section, "classLabel")
            if value:
                return _unquote(value).lower()
        return ""


def _unquote(value: str) -> str:
    return value.strip().strip('"').strip("'")


def parse_odf_bytes(data: bytes, virtual_path: str | Path) -> ODFDocument:
    """Parse an ODF byte stream as permissive legacy INI text."""
    text = data.decode("latin-1")
    sections: Dict[str, List[Tuple[str, str, int]]] = {}
    original_sections: Dict[str, str] = {}
    current: str | None = None

    section_re = re.compile(r"^\s*\[([^\]]+)\]\s*(?:;.*)?$")
    key_re = re.compile(r"^\s*([^;#=\s][^=]*?)\s*=\s*(.*?)\s*$")

    for line_no, line in enumerate(text.splitlines(), 1):
        sec = section_re.match(line)
        if sec:
            original = sec.group(1).strip()
            current = original.lower()
            original_sections.setdefault(current, original)
            sections.setdefault(current, [])
            continue

        if current is None:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        match = key_re.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        sections[current].append((key, value, line_no))

    return ODFDocument(path=Path(virtual_path), sections=sections, original_sections=original_sections)


def parse_odf(path: Path) -> ODFDocument:
    return parse_odf_bytes(path.read_bytes(), path)


def _issue(
    severity: str,
    doc: ODFDocument,
    section: str,
    key: str,
    message: str,
    suggestion: str = "",
    source: str = "",
    rule_id: str = "",
    line: int = 0,
) -> ODFIssue:
    return ODFIssue(
        severity=severity,
        filename=doc.path.name,
        section=section,
        key=key,
        message=message,
        suggestion=suggestion,
        source=source,
        rule_id=rule_id,
        line=line,
    )


def _rule_matches(doc: ODFDocument, rule: LoaderRule) -> bool:
    if rule.class_labels and doc.class_label() not in {label.lower() for label in rule.class_labels}:
        return False
    return all(doc.has_section(section) for section in rule.required_sections)


def _active_rule_section(doc: ODFDocument, rule: LoaderRule) -> tuple[str | None, bool]:
    """Return (section name, is_legacy) for the first present section in a rule."""
    if doc.has_section(rule.expected_section):
        return rule.expected_section, False
    for legacy in rule.legacy_sections:
        if doc.has_section(legacy):
            return doc.original_sections.get(legacy.lower(), legacy), True
    return None, False


def _validate_loader_rules(doc: ODFDocument) -> List[ODFIssue]:
    issues: List[ODFIssue] = []

    for rule in LOADER_RULES:
        if not _rule_matches(doc, rule):
            continue

        section, is_legacy = _active_rule_section(doc, rule)
        if section is None:
            # Absence alone is not an error yet: ODF inheritance may supply the
            # class-specific section from baseName. Until inheritance resolution
            # is implemented, only diagnose a canonical or known-legacy section
            # that is actually present in this file.
            continue

        if is_legacy:
            issues.append(_issue(
                rule.section_severity,
                doc,
                section,
                "",
                rule.section_message,
                f"Rename [{section}] to [{rule.expected_section}].",
                rule.source,
                rule.rule_id,
            ))

        keys = doc.keys(section)

        for alias in rule.key_aliases:
            entry = keys.get(alias.legacy.lower())
            if not entry:
                continue
            _value, line, original_key = entry
            # If the alias differs only by case, only flag the exact legacy
            # spelling encoded in the schema; this avoids inventing case rules.
            if original_key != alias.legacy:
                continue
            issues.append(_issue(
                alias.severity,
                doc,
                section,
                original_key,
                alias.message or f"'{original_key}' is not the Redux loader key spelling.",
                f"Use '{alias.canonical}'.",
                rule.source,
                rule.rule_id,
                line,
            ))

        # Required keys are enforced on the canonical loader section. A legacy
        # section may contain the key text, but Redux will not load it.
        if not is_legacy:
            canonical_keys = doc.keys(rule.expected_section)
            for required in rule.required_keys:
                if required.name.lower() not in canonical_keys or not _unquote(canonical_keys[required.name.lower()][0]):
                    issues.append(_issue(
                        required.severity,
                        doc,
                        rule.expected_section,
                        required.name,
                        required.message,
                        required.suggestion,
                        rule.source,
                        rule.rule_id,
                    ))

        for legacy_key in rule.legacy_keys:
            entry = keys.get(legacy_key.name.lower())
            if not entry:
                continue
            _value, line, original_key = entry
            issues.append(_issue(
                legacy_key.severity,
                doc,
                section,
                original_key,
                legacy_key.message,
                legacy_key.suggestion,
                rule.source,
                rule.rule_id,
                line,
            ))

    return issues


def _validate_references(doc: ODFDocument, available: set[str]) -> List[ODFIssue]:
    issues: List[ODFIssue] = []
    if not available:
        return issues

    for section, keyspec in REFERENCE_KEYS.items():
        if not doc.has_section(section):
            continue
        keys = doc.keys(section)
        for canonical_key, severity in keyspec.items():
            entry = keys.get(canonical_key.lower())
            if not entry:
                continue
            value, line, original_key = entry
            reference = _unquote(value)
            if not reference or reference.lower() in {"null", "none"}:
                continue
            target = reference.lower()
            if not target.endswith(".odf"):
                target += ".odf"
            if target in available:
                continue

            close = get_close_matches(target, sorted(available), n=1, cutoff=0.78)
            suggestion = f"Did you mean '{close[0]}'?" if close else "Add the referenced ODF or correct the name."
            label = "payload" if section.lower() == "flaremineclass" else "ODF"
            issues.append(_issue(
                severity,
                doc,
                section,
                original_key,
                f"Referenced {label} '{reference}' was not found in the scanned local/stock ODF namespace.",
                suggestion,
                f"{section} ODF dependency",
                "reference-check",
                line,
            ))

    return issues


def validate_document(doc: ODFDocument, available_odfs: Iterable[str] = ()) -> List[ODFIssue]:
    available = {name.lower() for name in available_odfs}
    issues = _validate_loader_rules(doc)
    issues.extend(_validate_references(doc, available))
    return issues


def _sort_issues(issues: List[ODFIssue]) -> List[ODFIssue]:
    order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    issues.sort(
        key=lambda x: (
            order.get(x.severity, 99),
            x.filename.lower(),
            x.line or 1_000_000,
            x.section.lower(),
            x.key.lower(),
        )
    )
    return issues


def validate_documents(documents: Sequence[ODFDocument], known_odfs: Iterable[str] = ()) -> List[ODFIssue]:
    available = {doc.path.name.lower() for doc in documents}
    available.update(name.lower() for name in known_odfs)
    issues: List[ODFIssue] = []
    for doc in documents:
        issues.extend(validate_document(doc, available))
    return _sort_issues(issues)


def validate_directory(
    directory: str | Path,
    filenames: Sequence[str] | None = None,
    known_odfs: Iterable[str] = (),
) -> List[ODFIssue]:
    root = Path(directory)
    paths = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".odf"]
    if filenames is not None:
        wanted = {Path(name).name.lower() for name in filenames}
        paths = [p for p in paths if p.name.lower() in wanted]
    paths.sort(key=lambda p: p.name.lower())

    documents: List[ODFDocument] = []
    issues: List[ODFIssue] = []
    for path in paths:
        try:
            documents.append(parse_odf(path))
        except OSError as exc:
            issues.append(ODFIssue(
                severity="ERROR",
                filename=path.name,
                section="",
                key="",
                message=f"Could not read ODF: {exc}",
                source="filesystem",
                rule_id="read-error",
            ))

    available = {p.name.lower() for p in paths}
    # The available namespace should include every local ODF even when only a
    # subset is being validated, so references can resolve against siblings.
    try:
        available.update(p.name.lower() for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".odf")
    except OSError:
        pass
    available.update(name.lower() for name in known_odfs)
    for doc in documents:
        issues.extend(validate_document(doc, available))
    return _sort_issues(issues)


def validate_zip(
    archive: str | Path,
    filenames: Sequence[str] | None = None,
    known_odfs: Iterable[str] = (),
) -> List[ODFIssue]:
    """Validate ODFs directly inside a ZIP without extracting files to disk."""
    wanted = None if filenames is None else {Path(name).name.lower() for name in filenames}
    documents: List[ODFDocument] = []
    issues: List[ODFIssue] = []

    try:
        with zipfile.ZipFile(archive, "r") as zf:
            odf_infos = [
                info for info in zf.infolist()
                if not info.is_dir() and Path(info.filename).suffix.lower() == ".odf"
            ]
            available = {Path(info.filename).name.lower() for info in odf_infos}
            available.update(name.lower() for name in known_odfs)
            for info in odf_infos:
                name = Path(info.filename).name
                if wanted is not None and name.lower() not in wanted:
                    continue
                try:
                    documents.append(parse_odf_bytes(zf.read(info), info.filename))
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    issues.append(ODFIssue(
                        severity="ERROR",
                        filename=name,
                        section="",
                        key="",
                        message=f"Could not read ODF from ZIP: {exc}",
                        source="ZIP archive",
                        rule_id="read-error",
                    ))
    except (OSError, zipfile.BadZipFile) as exc:
        return [ODFIssue(
            severity="ERROR",
            filename=Path(archive).name,
            section="",
            key="",
            message=f"Could not open ZIP: {exc}",
            source="ZIP archive",
            rule_id="archive-error",
        )]

    # Recompute from all archive names, including ODFs not selected for detailed
    # validation, so sibling dependencies still resolve.
    available = set(name.lower() for name in known_odfs)
    with zipfile.ZipFile(archive, "r") as zf:
        available.update(
            Path(info.filename).name.lower()
            for info in zf.infolist()
            if not info.is_dir() and Path(info.filename).suffix.lower() == ".odf"
        )
    for doc in documents:
        issues.extend(validate_document(doc, available))
    return _sort_issues(issues)


def _cli_main() -> int:
    import argparse
    import json
    from dataclasses import asdict

    parser = argparse.ArgumentParser(description="Validate Battlezone 98 Redux ODF files")
    parser.add_argument("path", help="ODF file, folder, or ZIP archive to validate")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON findings")
    args = parser.parse_args()

    try:
        from bzn_scan import STOCK_SET
        known = STOCK_SET
    except Exception:
        known = ()

    target = Path(args.path)
    if target.is_dir():
        issues = validate_directory(target, known_odfs=known)
    elif target.suffix.lower() == ".zip":
        issues = validate_zip(target, known_odfs=known)
    elif target.suffix.lower() == ".odf" and target.is_file():
        issues = validate_directory(target.parent, filenames=[target.name], known_odfs=known)
    else:
        parser.error("path must be an ODF file, directory, or ZIP archive")

    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    else:
        for issue in issues:
            location = issue.section
            if issue.key:
                location = f"{location}/{issue.key}" if location else issue.key
            line = f":{issue.line}" if issue.line else ""
            print(f"{issue.severity:8} {issue.filename}{line} {location} - {issue.message}")
            if issue.suggestion:
                print(f"         fix: {issue.suggestion}")
        if not issues:
            print("No ODF validation findings.")

    if any(issue.severity == "CRITICAL" for issue in issues):
        return 2
    if any(issue.severity == "ERROR" for issue in issues):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())

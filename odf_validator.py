"""Battlezone 98 Redux ODF validation.

The validator is intentionally conservative: it reports loader mismatches and
known crash-risk omissions without rewriting user files.  Rules in this module
should be backed by stock ODFs, source/decomp loader behavior, or a reproducible
runtime failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
import re
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class ODFIssue:
    severity: str
    filename: str
    section: str
    key: str
    message: str
    suggestion: str = ""
    source: str = ""


@dataclass
class ODFDocument:
    path: Path
    sections: Dict[str, List[Tuple[str, str, int]]]
    original_sections: Dict[str, str]

    def has_section(self, name: str) -> bool:
        return name.lower() in self.sections

    def keys(self, section: str) -> Mapping[str, Tuple[str, int]]:
        out: Dict[str, Tuple[str, int]] = {}
        for key, value, line in self.sections.get(section.lower(), []):
            out[key.lower()] = (value, line)
        return out


# Canonical section names exercised by the initial rule pack.  This is not yet
# the complete Redux loader schema; it is deliberately evidence-driven.
CANONICAL_SECTIONS = {
    "gameobjectclass": "GameObjectClass",
    "ordnanceclass": "OrdnanceClass",
    "weaponclass": "WeaponClass",
    "mineclass": "MineClass",
    "flaremineclass": "FlareMineClass",
    "magnetmineclass": "MagnetMineClass",
    "scavengerclass": "ScavengerClass",
    "flamepuffclass": "FlamePuffClass",
    "craftclass": "CraftClass",
    "hovercraftclass": "HoverCraftClass",
    "buildingclass": "BuildingClass",
}

# Known historical/legacy labels that Redux silently ignores for these loaders.
SECTION_RENAMES = {
    "gameobject": "GameObjectClass",
    "flarebuildingclass": "FlareMineClass",
    "magnetclass": "MagnetMineClass",
    "scavengercraftclass": "ScavengerClass",
    "flameclass": "FlamePuffClass",
}

# Keys whose spelling is known to matter in Redux loaders.  Lookup is case
# insensitive for validation because historical ODFs use inconsistent casing;
# this catches actual spelling changes rather than stylistic case differences.
KEY_RENAMES = {
    ("MagnetMineClass", "triggetdelay"): "triggerDelay",
}

FLAME_PUFF_KEYS = {
    "flameradius": "flameRadius",
    "flamedelay": "flameDelay",
    "flametexture": "flameTexture",
    "flameframes": "flameFrames",
}

FLAME_LEGACY_KEYS = {
    "flamelength": "flameLength",
    "variance": "variance",
    "shotcolor": "shotColor",
}


def parse_odf(path: Path) -> ODFDocument:
    """Parse an ODF as a permissive INI-like file while preserving duplicates."""
    raw = path.read_bytes()
    # ODFs are legacy ASCII/ANSI files. latin-1 is lossless for byte values and
    # avoids rejecting old community files that are not valid UTF-8.
    text = raw.decode("latin-1")

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

    return ODFDocument(path=path, sections=sections, original_sections=original_sections)


def _issue(severity: str, doc: ODFDocument, section: str, key: str, message: str,
           suggestion: str = "", source: str = "") -> ODFIssue:
    return ODFIssue(
        severity=severity,
        filename=doc.path.name,
        section=section,
        key=key,
        message=message,
        suggestion=suggestion,
        source=source,
    )


def validate_document(doc: ODFDocument, available_odfs: Iterable[str] = ()) -> List[ODFIssue]:
    issues: List[ODFIssue] = []
    available = {name.lower() for name in available_odfs}

    # Section-loader mismatches.  These are high signal because Redux matches
    # loader section hashes; an unrecognized section is simply never consumed.
    for lower, original in doc.original_sections.items():
        replacement = SECTION_RENAMES.get(lower)
        if replacement:
            severity = "ERROR"
            message = f"Redux does not use [{original}] for this class; the section is silently ignored."
            source = "Redux loader section name"
            if replacement == "FlareMineClass":
                severity = "CRITICAL"
                message = (
                    f"Redux expects [{replacement}], not [{original}]. Ignoring this section can leave "
                    "the flare payload OrdnanceClass pointer null and crash FlareMine::Update()."
                )
                source = "FlareMineClass::Load / FlareMine::Update runtime crash trace"
            issues.append(_issue(
                severity, doc, original, "", message,
                f"Rename [{original}] to [{replacement}].", source,
            ))

    # Validate known misspelled keys against the section Redux actually wants.
    for lower, original in doc.original_sections.items():
        effective_section = SECTION_RENAMES.get(lower, CANONICAL_SECTIONS.get(lower, original))
        keys = doc.keys(original)
        for key_lower in keys:
            replacement = KEY_RENAMES.get((effective_section, key_lower))
            if replacement:
                issues.append(_issue(
                    "ERROR", doc, original, key_lower,
                    f"'{key_lower}' is not read by the Redux {effective_section} loader.",
                    f"Use '{replacement}'.", "Redux loader key spelling",
                ))

    # FlareMine payload is dereferenced by runtime update code.  Report a
    # missing payload even when the section itself is otherwise valid.
    flare_sections = []
    if doc.has_section("FlareMineClass"):
        flare_sections.append("FlareMineClass")
    if doc.has_section("FlareBuildingClass"):
        # Still inspect it so the error can explain why the apparent payload is
        # not sufficient.
        flare_sections.append("FlareBuildingClass")
    for section in flare_sections:
        keys = doc.keys(section)
        payload = keys.get("payloadname", ("", 0))[0].strip().strip('"').strip("'")
        if section == "FlareMineClass" and not payload:
            issues.append(_issue(
                "CRITICAL", doc, section, "payloadName",
                "FlareMineClass has no payloadName; runtime flare update can dereference a null payload class.",
                "Set payloadName to a valid ordnance ODF base name.",
                "FlareMineClass::Load / FlareMine::Update runtime crash trace",
            ))
        if payload and available:
            target = payload.lower()
            if not target.endswith(".odf"):
                target += ".odf"
            if target not in available:
                issues.append(_issue(
                    "ERROR", doc, section, "payloadName",
                    f"Referenced payload '{payload}' was not found in the scanned directory.",
                    "Add the referenced ODF or correct payloadName.", "ODF dependency check",
                ))

    # Flame puff loader migration: old [flameClass] sections and several old
    # fields are accepted by neither the Redux FlamePuffClass loader nor its
    # stock ODF contract.
    flame_section = None
    if doc.has_section("FlamePuffClass"):
        flame_section = "FlamePuffClass"
    elif doc.has_section("flameClass"):
        flame_section = "flameClass"
    if flame_section:
        keys = doc.keys(flame_section)
        for legacy in FLAME_LEGACY_KEYS:
            if legacy in keys:
                issues.append(_issue(
                    "WARNING", doc, flame_section, legacy,
                    f"'{legacy}' is a legacy flame field and is not part of the Redux FlamePuffClass key set.",
                    "Use the Redux flameRadius/flameDelay/flameTexture/flameFrames model as appropriate.",
                    "Redux FlamePuffClass loader / stock flame ODFs",
                ))

    # Catch the exact historical typo from AbsoZero.  Generic dependency
    # extraction cannot infer arbitrary resource types, so start with the
    # explosion keys that are known ODF references.
    ord_keys = doc.keys("OrdnanceClass") if doc.has_section("OrdnanceClass") else {}
    for key in ("xplground", "xplvehicle", "xplbuilding"):
        if key not in ord_keys:
            continue
        value = ord_keys[key][0].strip().strip('"').strip("'")
        if not value or not available:
            continue
        target = value.lower()
        if not target.endswith(".odf"):
            target += ".odf"
        if target in available:
            continue
        # Stock names are not necessarily in the mission directory, but a very
        # close local/known name is useful enough to suggest without rewriting.
        candidates = sorted(available)
        close = get_close_matches(target, candidates, n=1, cutoff=0.80)
        suggestion = f"Did you mean '{close[0]}'?" if close else "Verify the explosion ODF name."
        issues.append(_issue(
            "WARNING", doc, "OrdnanceClass", key,
            f"Referenced explosion ODF '{value}' was not found in the scanned directory.",
            suggestion, "OrdnanceClass explosion dependency",
        ))

    return issues


def validate_directory(directory: str | Path, filenames: Sequence[str] | None = None) -> List[ODFIssue]:
    root = Path(directory)
    if filenames is None:
        paths = sorted(root.glob("*.odf"), key=lambda p: p.name.lower())
    else:
        wanted = {name.lower() for name in filenames}
        paths = [p for p in root.glob("*.odf") if p.name.lower() in wanted]
        paths.sort(key=lambda p: p.name.lower())

    available = {p.name.lower() for p in root.glob("*.odf")}
    issues: List[ODFIssue] = []
    for path in paths:
        try:
            doc = parse_odf(path)
            issues.extend(validate_document(doc, available))
        except OSError as exc:
            issues.append(ODFIssue(
                severity="ERROR", filename=path.name, section="", key="",
                message=f"Could not read ODF: {exc}", source="filesystem",
            ))

    order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    issues.sort(key=lambda x: (order.get(x.severity, 99), x.filename.lower(), x.section.lower(), x.key.lower()))
    return issues

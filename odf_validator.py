"""Battlezone 98 Redux ODF validation.

The validator is intentionally conservative: it reports loader mismatches and
known crash-risk omissions without rewriting user files. Rules in this module
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

    def value(self, section: str, key: str, default: str = "") -> str:
        return self.keys(section).get(key.lower(), (default, 0))[0]

    def class_label(self) -> str:
        for section in ("GameObjectClass", "GameObject", "OrdnanceClass", "WeaponClass"):
            value = self.value(section, "classLabel")
            if value:
                return _unquote(value).lower()
        return ""


def _unquote(value: str) -> str:
    return value.strip().strip('"').strip("'")


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


def _section_issue(doc: ODFDocument, old: str, new: str, *, critical: bool = False,
                   source: str = "Redux loader section name") -> ODFIssue:
    severity = "CRITICAL" if critical else "ERROR"
    if critical:
        message = (
            f"Redux expects [{new}], not [{old}]. Ignoring this section can leave the "
            "flare payload OrdnanceClass pointer null and crash FlareMine::Update()."
        )
    else:
        message = f"Redux expects [{new}], not [{old}]; [{old}] is silently ignored by this loader path."
    return _issue(severity, doc, old, "", message, f"Rename [{old}] to [{new}].", source)


def validate_document(doc: ODFDocument, available_odfs: Iterable[str] = ()) -> List[ODFIssue]:
    issues: List[ODFIssue] = []
    available = {name.lower() for name in available_odfs}
    label = doc.class_label()

    # GameObject is an old section label; Redux object-class data is loaded from
    # GameObjectClass. This is what causes an otherwise populated object to reach
    # class creation with no usable classLabel.
    if doc.has_section("GameObject"):
        issues.append(_section_issue(doc, doc.original_sections["gameobject"], "GameObjectClass"))
        game_keys = doc.keys("GameObject")
        if "basename" in game_keys:
            issues.append(_issue(
                "WARNING", doc, doc.original_sections["gameobject"], "basename",
                "Use Redux's canonical baseName spelling when migrating this GameObject section.",
                "Rename the key to 'baseName' while converting the section to [GameObjectClass].",
                "Redux GameObjectClass loader / stock ODF contract",
            ))

    # The fatal AbsoZero case. Redux loads flare-specific data from
    # FlareMineClass; FlareBuildingClass is never consumed. If payloadName never
    # reaches the class object, FlareMine::Update dereferences a null payload.
    if label == "flare" and doc.has_section("FlareBuildingClass"):
        issues.append(_section_issue(
            doc, doc.original_sections["flarebuildingclass"], "FlareMineClass",
            critical=True,
            source="FlareMineClass::Load / FlareMine::Update runtime crash trace",
        ))

    # MagnetClass also exists on non-mine objects, so only reinterpret it when
    # the ODF is the mine/ordnance path (OrdnanceClass + MineClass + magnet).
    magnet_mine = (
        label == "magnet"
        and doc.has_section("OrdnanceClass")
        and doc.has_section("MineClass")
    )
    if magnet_mine and doc.has_section("MagnetClass"):
        old = doc.original_sections["magnetclass"]
        issues.append(_section_issue(doc, old, "MagnetMineClass"))
        if "triggetdelay" in doc.keys("MagnetClass"):
            issues.append(_issue(
                "ERROR", doc, old, "triggetDelay",
                "'triggetDelay' is not read by the Redux MagnetMineClass loader.",
                "Use 'triggerDelay'.", "Redux MagnetMineClass loader key spelling",
            ))
    elif magnet_mine and doc.has_section("MagnetMineClass"):
        if "triggetdelay" in doc.keys("MagnetMineClass"):
            issues.append(_issue(
                "ERROR", doc, "MagnetMineClass", "triggetDelay",
                "'triggetDelay' is not read by the Redux MagnetMineClass loader.",
                "Use 'triggerDelay'.", "Redux MagnetMineClass loader key spelling",
            ))

    # ScavengerCraftClass is the legacy name used by this mission; Redux's
    # scavenger-specific loader section is ScavengerClass.
    if label == "scavenger" and doc.has_section("ScavengerCraftClass"):
        issues.append(_section_issue(
            doc, doc.original_sections["scavengercraftclass"], "ScavengerClass"
        ))

    # flameClass is not universally a FlamePuffClass alias (switcher ODFs may
    # carry their own legacy flame data), so only apply this rule to flamepuff.
    flame_puff = label == "flamepuff" and doc.has_section("OrdnanceClass")
    if flame_puff and doc.has_section("flameClass"):
        old = doc.original_sections["flameclass"]
        issues.append(_section_issue(doc, old, "FlamePuffClass"))
        flame_section = old
    elif flame_puff and doc.has_section("FlamePuffClass"):
        flame_section = "FlamePuffClass"
    else:
        flame_section = None

    if flame_section:
        keys = doc.keys(flame_section)
        for legacy in ("flamelength", "variance", "shotcolor"):
            if legacy in keys:
                issues.append(_issue(
                    "WARNING", doc, flame_section, legacy,
                    f"'{legacy}' is a legacy flame field and is not part of the Redux FlamePuffClass key set.",
                    "Use flameRadius/flameDelay/flameTexture/flameFrames as appropriate.",
                    "Redux FlamePuffClass loader / stock flame ODF contract",
                ))

    # FlareMine payload is dereferenced by runtime update code. Report a missing
    # payload on the actual Redux section, and validate any named payload against
    # the combined local + known-stock namespace supplied by the caller.
    if doc.has_section("FlareMineClass"):
        payload = _unquote(doc.value("FlareMineClass", "payloadName"))
        if not payload:
            issues.append(_issue(
                "CRITICAL", doc, "FlareMineClass", "payloadName",
                "FlareMineClass has no payloadName; runtime flare update can dereference a null payload class.",
                "Set payloadName to a valid ordnance ODF base name.",
                "FlareMineClass::Load / FlareMine::Update runtime crash trace",
            ))
        elif available:
            target = payload.lower()
            if not target.endswith(".odf"):
                target += ".odf"
            if target not in available:
                issues.append(_issue(
                    "ERROR", doc, "FlareMineClass", "payloadName",
                    f"Referenced payload '{payload}' was not found in the scanned local/stock ODF namespace.",
                    "Add the referenced ODF or correct payloadName.", "ODF dependency check",
                ))

    # Explosion keys are ODF references. Checking them against local files plus
    # the stock ODF set catches misspellings such as xmlasbld -> xlasbld while
    # avoiding false positives for ordinary stock explosion assets.
    ord_keys = doc.keys("OrdnanceClass") if doc.has_section("OrdnanceClass") else {}
    for key in ("xplground", "xplvehicle", "xplbuilding"):
        if key not in ord_keys:
            continue
        value = _unquote(ord_keys[key][0])
        if not value or not available:
            continue
        target = value.lower()
        if not target.endswith(".odf"):
            target += ".odf"
        if target in available:
            continue
        close = get_close_matches(target, sorted(available), n=1, cutoff=0.78)
        suggestion = f"Did you mean '{close[0]}'?" if close else "Verify the explosion ODF name."
        issues.append(_issue(
            "WARNING", doc, "OrdnanceClass", key,
            f"Referenced explosion ODF '{value}' was not found in the scanned local/stock ODF namespace.",
            suggestion, "OrdnanceClass explosion dependency",
        ))

    return issues


def validate_directory(
    directory: str | Path,
    filenames: Sequence[str] | None = None,
    known_odfs: Iterable[str] = (),
) -> List[ODFIssue]:
    root = Path(directory)
    if filenames is None:
        paths = sorted(root.glob("*.odf"), key=lambda p: p.name.lower())
    else:
        wanted = {name.lower() for name in filenames}
        paths = [p for p in root.glob("*.odf") if p.name.lower() in wanted]
        paths.sort(key=lambda p: p.name.lower())

    available = {p.name.lower() for p in root.glob("*.odf")}
    available.update(name.lower() for name in known_odfs)

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

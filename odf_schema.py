"""Evidence-backed Battlezone 98 Redux ODF loader schema.

This module is intentionally data-only. The validator consumes these curated
rules so new loader findings can be added without growing a chain of one-off
conditionals. Research/mining output is evidence, not policy: only reviewed
entries should become hard diagnostics here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


# Confidence values used by the mined corpus and curated rules. ``inferred`` and
# hash-only discoveries must never become hard validator diagnostics merely by
# appearing in research output.
EVIDENCE_CONFIDENCE = (
    "confirmed-code",
    "code+stock",
    "stock-only",
    "inferred",
)


@dataclass(frozen=True)
class EvidenceRef:
    """Machine-readable provenance for a curated validator rule.

    Repository/path are optional because Redux executable evidence may only have
    a recovered symbol/address until the corresponding decomp artifact is
    imported. ``summary`` should state exactly what the cited evidence proves.
    """

    kind: str
    confidence: str
    summary: str
    repository: str = ""
    path: str = ""
    symbol: str = ""
    address: str = ""
    commit: str = ""
    stock_file: str = ""
    runtime_case: str = ""


@dataclass(frozen=True)
class KeyAlias:
    legacy: str
    canonical: str
    severity: str = "ERROR"
    message: str = ""
    legacy_only: bool = False


@dataclass(frozen=True)
class RequiredKey:
    name: str
    severity: str
    message: str
    suggestion: str


@dataclass(frozen=True)
class LegacyKey:
    name: str
    severity: str
    message: str
    suggestion: str


@dataclass(frozen=True)
class LoaderRule:
    rule_id: str
    expected_section: str
    legacy_sections: Tuple[str, ...] = ()
    class_labels: Tuple[str, ...] = ()
    required_sections: Tuple[str, ...] = ()
    section_severity: str = "ERROR"
    section_message: str = ""
    source: str = ""
    evidence: Tuple[EvidenceRef, ...] = ()
    key_aliases: Tuple[KeyAlias, ...] = ()
    required_keys: Tuple[RequiredKey, ...] = ()
    legacy_keys: Tuple[LegacyKey, ...] = ()
    # Retained for schema compatibility. Absence-based section claims should be
    # used only when the actual engine loader/prototype semantics prove them.
    missing_section_severity: str = ""
    missing_section_message: str = ""
    missing_section_suggestion: str = ""


LOADER_RULES = (
    LoaderRule(
        rule_id="game-object-root",
        expected_section="GameObjectClass",
        legacy_sections=("GameObject",),
        section_severity="ERROR",
        section_message=(
            "Redux object-class data is dispatched from [GameObjectClass]; the "
            "legacy [GameObject] section is not consumed by this loader path."
        ),
        source="Redux GameObjectClass dispatch / mined loader contract",
        key_aliases=(
            KeyAlias(
                legacy="basename",
                canonical="baseName",
                severity="WARNING",
                message=(
                    "Use Redux's canonical baseName spelling when migrating this "
                    "legacy section. baseName is not ODF file inheritance."
                ),
                legacy_only=True,
            ),
        ),
    ),
    LoaderRule(
        rule_id="flare-mine",
        expected_section="FlareMineClass",
        legacy_sections=("FlareBuildingClass",),
        class_labels=("flare",),
        required_sections=("MineClass",),
        section_severity="CRITICAL",
        section_message=(
            "Redux loads flare-specific data from [FlareMineClass]. The legacy "
            "[FlareBuildingClass] section has no loader reader, so payloadName can "
            "remain null and the flare firing path can dereference a null payload "
            "OrdnanceClass pointer."
        ),
        source=(
            "Redux decomp: FlareMineClass::Load 0x004D2B10 -> "
            "FlareMine::Update 0x004D2E90 -> OrdnanceClass::Build 0x00586FF0"
        ),
        evidence=(
            EvidenceRef(
                kind="redux-decomp",
                confidence="confirmed-code",
                symbol="FlareMineClass::Load",
                address="0x004D2B10",
                summary=(
                    "FlareMine loader resolves payloadName into the payload "
                    "OrdnanceClass pointer used by the runtime object."
                ),
            ),
            EvidenceRef(
                kind="redux-decomp",
                confidence="confirmed-code",
                symbol="FlareMine::Update(float)",
                address="0x004D2E90",
                summary=(
                    "FlareMine update follows the class payload pointer when the "
                    "mine fires and reaches the ordnance build path."
                ),
            ),
            EvidenceRef(
                kind="redux-decomp",
                confidence="confirmed-code",
                symbol="OrdnanceClass::Build",
                address="0x00586FF0",
                summary=(
                    "A null payload class reaches an unguarded dereference; the "
                    "confirmed AbsoZero fault occurs at 0x00586FFC reading +0x38."
                ),
            ),
            EvidenceRef(
                kind="runtime-repro",
                confidence="code+stock",
                runtime_case="AbsoZero flare section repair",
                summary=(
                    "Changing [FlareBuildingClass] to [FlareMineClass] allowed the "
                    "mission to initialize and run without the immediate flare crash."
                ),
            ),
        ),
        required_keys=(
            RequiredKey(
                name="payloadName",
                severity="CRITICAL",
                message=(
                    "FlareMineClass has no payloadName; the firing path can reach "
                    "OrdnanceClass::Build with a null payload class."
                ),
                suggestion="Set payloadName to a valid ordnance ODF base name.",
            ),
        ),
    ),
    LoaderRule(
        rule_id="magnet-mine",
        expected_section="MagnetMineClass",
        legacy_sections=("MagnetClass",),
        class_labels=("magnet",),
        required_sections=("OrdnanceClass", "MineClass"),
        section_severity="ERROR",
        section_message=(
            "This is the magnet mine/ordnance loader path. Redux reads mine-specific "
            "magnet parameters from [MagnetMineClass], not [MagnetClass]."
        ),
        source="Redux MagnetMineClass loader / mined loader contract",
        key_aliases=(
            KeyAlias(
                legacy="triggetDelay",
                canonical="triggerDelay",
                severity="ERROR",
                message=(
                    "The misspelled triggetDelay key has no reader; the Redux "
                    "MagnetMineClass loader reads triggerDelay."
                ),
            ),
        ),
    ),
    LoaderRule(
        rule_id="scavenger",
        expected_section="ScavengerClass",
        legacy_sections=("ScavengerCraftClass",),
        class_labels=("scavenger",),
        required_sections=("CraftClass",),
        section_severity="ERROR",
        section_message=(
            "Redux reads scavenger-specific fields from [ScavengerClass]; "
            "[ScavengerCraftClass] has no loader reader."
        ),
        source="Redux ScavengerClass loader / mined loader contract",
    ),
    LoaderRule(
        rule_id="flame-puff",
        expected_section="FlamePuffClass",
        legacy_sections=("flameClass",),
        class_labels=("flamepuff",),
        required_sections=("OrdnanceClass",),
        section_severity="ERROR",
        section_message=(
            "This ODF is classLabel=flamepuff. Redux reads flame-puff data from "
            "[FlamePuffClass], not the legacy [flameClass] section."
        ),
        source="Redux FlamePuffClass loader / mined loader contract",
        key_aliases=(
            KeyAlias(
                legacy="flameDelay",
                canonical="frameDelay",
                severity="WARNING",
                message=(
                    "flameDelay has no recovered reader on the Redux FlamePuffClass "
                    "loader; the code reads frameDelay."
                ),
            ),
        ),
        legacy_keys=(
            LegacyKey(
                name="flameLength",
                severity="WARNING",
                message="flameLength is not part of the recovered Redux FlamePuffClass key set.",
                suggestion="Remove or replace it only after matching the intended effect to a code-read FlamePuffClass field.",
            ),
            LegacyKey(
                name="variance",
                severity="WARNING",
                message="variance is not part of the recovered Redux FlamePuffClass key set.",
                suggestion="Remove or replace it only after matching the intended effect to a code-read FlamePuffClass field.",
            ),
            LegacyKey(
                name="shotColor",
                severity="WARNING",
                message="shotColor is not part of the recovered Redux FlamePuffClass key set.",
                suggestion="Remove or replace it only after matching the intended effect to a code-read FlamePuffClass field.",
            ),
        ),
    ),
)


# ODF-valued keys that can be checked against the combined local + stock ODF
# namespace. These are physical-file dependency checks; no baseName file merging
# is performed.
REFERENCE_KEYS = {
    "FlareMineClass": {
        "payloadName": "ERROR",
    },
    "OrdnanceClass": {
        "xplGround": "WARNING",
        "xplVehicle": "WARNING",
        "xplBuilding": "WARNING",
    },
}


SCHEMA_VERSION = 3

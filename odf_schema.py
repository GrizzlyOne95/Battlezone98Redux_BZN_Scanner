"""Evidence-backed Battlezone 98 Redux ODF loader schema.

This module is intentionally data-only. The validator consumes these rules so
new loader findings can be added without growing a chain of one-off conditionals.
Each rule should be traceable to structured provenance in odf_evidence.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class KeyAlias:
    legacy: str
    canonical: str
    severity: str = "ERROR"
    message: str = ""
    legacy_only: bool = False
    evidence_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RequiredKey:
    name: str
    severity: str
    message: str
    suggestion: str
    evidence_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class LegacyKey:
    name: str
    severity: str
    message: str
    suggestion: str
    evidence_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ReferenceKey:
    name: str
    severity: str
    evidence_ids: Tuple[str, ...] = ("odf-reference-resolution",)


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
    evidence_ids: Tuple[str, ...] = ()
    key_aliases: Tuple[KeyAlias, ...] = ()
    required_keys: Tuple[RequiredKey, ...] = ()
    legacy_keys: Tuple[LegacyKey, ...] = ()
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
            "Redux object-class data is loaded from [GameObjectClass]; the legacy "
            "[GameObject] section is not consumed by this loader path."
        ),
        source="Redux GameObjectClass loader / stock ODF contract",
        evidence_ids=("redux-gameobjectclass-contract",),
        key_aliases=(
            KeyAlias(
                legacy="basename",
                canonical="baseName",
                severity="WARNING",
                message="Use Redux's canonical baseName spelling when migrating this legacy section.",
                legacy_only=True,
                evidence_ids=("redux-gameobjectclass-contract", "odf-basename-inheritance"),
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
            "Redux loads flare-specific data from [FlareMineClass]. If a legacy "
            "section is ignored, payloadName never reaches the class object and "
            "FlareMine::Update() can dereference a null payload OrdnanceClass pointer."
        ),
        source="FlareMineClass::Load / FlareMine::Update runtime crash trace",
        evidence_ids=(
            "redux-flaremine-load",
            "redux-flaremine-update-null-payload",
            "stock-flare-section-contract",
            "absozero-flare-crash-repro",
        ),
        required_keys=(
            RequiredKey(
                name="payloadName",
                severity="CRITICAL",
                message=(
                    "FlareMineClass has no payloadName; runtime flare update can "
                    "dereference a null payload class."
                ),
                suggestion="Set payloadName to a valid ordnance ODF base name.",
                evidence_ids=(
                    "redux-flaremine-load",
                    "redux-flaremine-update-null-payload",
                    "absozero-flare-crash-repro",
                ),
            ),
        ),
        missing_section_severity="CRITICAL",
        missing_section_message=(
            "The fully resolved local inheritance chain has no [FlareMineClass]. "
            "For a flare mine this leaves no loader path to initialize payloadName, "
            "which can produce the confirmed null-payload FlareMine::Update() crash."
        ),
        missing_section_suggestion="Add [FlareMineClass] with a valid payloadName, or inherit it from a valid parent ODF.",
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
        source="Redux MagnetMineClass loader / stock magnet-mine ODF contract",
        evidence_ids=("redux-magnetmine-contract",),
        key_aliases=(
            KeyAlias(
                legacy="triggetDelay",
                canonical="triggerDelay",
                severity="ERROR",
                message="The misspelled triggetDelay key is not read by the Redux MagnetMineClass loader.",
                evidence_ids=("redux-magnetmine-contract",),
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
            "[ScavengerCraftClass] is a legacy section name."
        ),
        source="Redux ScavengerClass loader / stock scavenger ODF contract",
        evidence_ids=("redux-scavenger-contract",),
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
        source="Redux FlamePuffClass loader / stock flame-puff ODF contract",
        evidence_ids=("redux-flamepuff-contract",),
        legacy_keys=(
            LegacyKey(
                name="flameLength",
                severity="WARNING",
                message="flameLength is not part of the Redux FlamePuffClass key set.",
                suggestion="Use the Redux flameRadius/flameDelay/flameTexture/flameFrames model as appropriate.",
                evidence_ids=("redux-flamepuff-contract",),
            ),
            LegacyKey(
                name="variance",
                severity="WARNING",
                message="variance is not part of the Redux FlamePuffClass key set.",
                suggestion="Use the Redux flameRadius/flameDelay/flameTexture/flameFrames model as appropriate.",
                evidence_ids=("redux-flamepuff-contract",),
            ),
            LegacyKey(
                name="shotColor",
                severity="WARNING",
                message="shotColor is not part of the Redux FlamePuffClass key set.",
                suggestion="Use the Redux flameRadius/flameDelay/flameTexture/flameFrames model as appropriate.",
                evidence_ids=("redux-flamepuff-contract",),
            ),
        ),
    ),
)


REFERENCE_KEYS = {
    "FlareMineClass": (
        ReferenceKey(
            name="payloadName",
            severity="ERROR",
            evidence_ids=("redux-flaremine-load", "odf-reference-resolution"),
        ),
    ),
    "OrdnanceClass": (
        ReferenceKey(name="xplGround", severity="WARNING"),
        ReferenceKey(name="xplVehicle", severity="WARNING"),
        ReferenceKey(name="xplBuilding", severity="WARNING"),
    ),
}


SCHEMA_VERSION = 3

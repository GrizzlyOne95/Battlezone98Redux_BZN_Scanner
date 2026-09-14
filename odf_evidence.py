"""Structured provenance for ODF validation rules.

Evidence entries are intentionally conservative. Exact native addresses and
repository paths are recorded only when they have been verified; an empty field
means the checker knows the evidence category/claim but does not pretend to know
an exact location yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class ODFEvidence:
    evidence_id: str
    kind: str
    title: str
    detail: str
    function: str = ""
    address: str = ""
    related_addresses: Tuple[str, ...] = ()
    repository: str = ""
    path: str = ""

    def summary(self) -> str:
        parts = [f"[{self.kind}] {self.title}"]
        if self.function:
            location = self.function
            if self.address:
                location += f" @ {self.address}"
            parts.append(location)
        elif self.address:
            parts.append(self.address)
        if self.related_addresses:
            parts.append("related: " + ", ".join(self.related_addresses))
        if self.repository:
            repo = self.repository
            if self.path:
                repo += f"/{self.path}"
            parts.append(repo)
        parts.append(self.detail)
        return " — ".join(parts)


EVIDENCE: Dict[str, ODFEvidence] = {
    "redux-flaremine-load": ODFEvidence(
        evidence_id="redux-flaremine-load",
        kind="decomp",
        title="Redux flare payload loader",
        function="FlareMineClass::Load",
        address="0x004D2B10",
        repository="GrizzlyOne95/BZ1_Source",
        detail=(
            "The recovered Redux loader populates the flare payload OrdnanceClass "
            "from payloadName only through the FlareMineClass loader section. A "
            "legacy/unconsumed section therefore does not initialize that field."
        ),
    ),
    "redux-flaremine-update-null-payload": ODFEvidence(
        evidence_id="redux-flaremine-update-null-payload",
        kind="decomp",
        title="Redux flare update null-payload dereference path",
        function="FlareMine::Update(float)",
        address="0x004D2E90",
        related_addresses=("call 0x004D3093", "callee 0x00586FF0", "fault 0x00586FFC"),
        repository="GrizzlyOne95/BZ1_Source",
        detail=(
            "Update reads the FlareMineClass pointer from the object, then its "
            "payload OrdnanceClass pointer at class offset +0x168. The downstream "
            "call dereferences the payload object; a null payload produces the "
            "confirmed read-at-0x38 access violation."
        ),
    ),
    "absozero-flare-crash-repro": ODFEvidence(
        evidence_id="absozero-flare-crash-repro",
        kind="runtime-repro",
        title="AbsoZero flare crash reproduction",
        detail=(
            "Legacy AbsoZero flare ODFs used [FlareBuildingClass]. Renaming that "
            "section to [FlareMineClass] allowed payload loading and eliminated the "
            "immediate simulation-start crash in live Redux validation."
        ),
    ),
    "stock-flare-section-contract": ODFEvidence(
        evidence_id="stock-flare-section-contract",
        kind="stock-contract",
        title="Stock Redux flare ODF section contract",
        detail="The stock Redux flare ODF uses [FlareMineClass] for flare-specific fields.",
    ),
    "redux-gameobjectclass-contract": ODFEvidence(
        evidence_id="redux-gameobjectclass-contract",
        kind="loader-contract",
        title="Redux GameObjectClass root contract",
        repository="GrizzlyOne95/BZ1_Source",
        detail=(
            "Recovered Redux loader behavior and stock ODFs use [GameObjectClass] "
            "for the object-class root. No exact native function address is recorded "
            "here until independently verified."
        ),
    ),
    "redux-magnetmine-contract": ODFEvidence(
        evidence_id="redux-magnetmine-contract",
        kind="loader-contract",
        title="Redux MagnetMineClass contract",
        repository="GrizzlyOne95/BZ1_Source",
        detail=(
            "Recovered Redux/stock magnet-mine behavior uses [MagnetMineClass] and "
            "triggerDelay for the mine/ordnance path. Building magnets are a distinct "
            "path and are intentionally excluded by the schema context."
        ),
    ),
    "redux-scavenger-contract": ODFEvidence(
        evidence_id="redux-scavenger-contract",
        kind="loader-contract",
        title="Redux ScavengerClass contract",
        repository="GrizzlyOne95/BZ1_Source",
        detail=(
            "Recovered Redux loader behavior and stock scavenger ODFs use "
            "[ScavengerClass], not the legacy [ScavengerCraftClass] section."
        ),
    ),
    "redux-flamepuff-contract": ODFEvidence(
        evidence_id="redux-flamepuff-contract",
        kind="loader-contract",
        title="Redux FlamePuffClass contract",
        repository="GrizzlyOne95/BZ1_Source",
        detail=(
            "Recovered Redux loader behavior and stock flame-puff ODFs use "
            "[FlamePuffClass] and the Redux flameRadius/flameDelay/flameTexture/"
            "flameFrames model."
        ),
    ),
    "odf-reference-resolution": ODFEvidence(
        evidence_id="odf-reference-resolution",
        kind="package-check",
        title="ODF reference namespace validation",
        detail=(
            "The referenced ODF name is checked against the combined scanned local "
            "package and known stock ODF filename namespace. Near-miss suggestions "
            "are advisory and never rewrite files."
        ),
    ),
    "odf-basename-inheritance": ODFEvidence(
        evidence_id="odf-basename-inheritance",
        kind="loader-contract",
        title="Canonical baseName inheritance contract",
        detail=(
            "The scanner follows only exact canonical baseName declarations and "
            "resolves proven local parent chains. Opaque stock parents are not "
            "treated as if their contents were known."
        ),
    ),
}


def get_evidence(evidence_id: str) -> ODFEvidence | None:
    return EVIDENCE.get(evidence_id)


def resolve_evidence(evidence_ids: Iterable[str]) -> Tuple[ODFEvidence, ...]:
    return tuple(EVIDENCE[eid] for eid in evidence_ids if eid in EVIDENCE)


def validate_evidence_ids(evidence_ids: Iterable[str]) -> Tuple[str, ...]:
    return tuple(eid for eid in evidence_ids if eid not in EVIDENCE)

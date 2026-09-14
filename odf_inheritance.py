"""Conservative local ODF baseName inheritance resolution.

Only the exact canonical `baseName` key participates. This is intentional: old
community ODFs frequently contain lowercase `basename`, and Redux does not treat
that spelling as the canonical inheritance field.

The resolver understands local chains fully. A parent that exists only in the
known stock namespace is marked opaque because the scanner currently ships stock
names, not the complete stock ODF contents. Missing and cyclic parents are
reported separately so callers never need to guess effective values.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT_SECTIONS = ("GameObjectClass", "OrdnanceClass", "WeaponClass")


@dataclass(frozen=True)
class BaseReference:
    parent: str
    section: str
    line: int


@dataclass(frozen=True)
class InheritanceState:
    status: str  # complete | opaque | missing | cycle | ambiguous
    chain: Tuple[Any, ...]  # child -> local parent -> ...
    target: str = ""
    cycle: Tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.status == "complete"


@dataclass
class InheritanceGraph:
    states: Dict[str, InheritanceState]
    duplicates: Dict[str, Tuple[Any, ...]]

    def state_for(self, doc: Any) -> InheritanceState:
        return self.states.get(_doc_id(doc), InheritanceState("complete", (doc,)))


def _doc_id(doc: Any) -> str:
    return str(doc.path).replace("\\", "/").lower()


def _odf_name(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if not value:
        return ""
    name = Path(value).name
    if not name.lower().endswith(".odf"):
        name += ".odf"
    return name.lower()


def canonical_base_reference(doc: Any) -> BaseReference | None:
    """Return the first exact `baseName` on a canonical root section."""
    for section in ROOT_SECTIONS:
        if not doc.has_section(section):
            continue
        for key, value, line in doc.entries(section):
            if key == "baseName":
                parent = _odf_name(value)
                if parent:
                    return BaseReference(parent=parent, section=section, line=line)
    return None


def build_inheritance_graph(documents: Sequence[Any], known_odfs: Iterable[str] = ()) -> InheritanceGraph:
    known = {_odf_name(name) for name in known_odfs if _odf_name(name)}
    by_name: Dict[str, List[Any]] = {}
    for doc in documents:
        by_name.setdefault(doc.path.name.lower(), []).append(doc)

    duplicates = {
        name: tuple(items)
        for name, items in by_name.items()
        if len(items) > 1
    }
    unique = {
        name: items[0]
        for name, items in by_name.items()
        if len(items) == 1
    }

    cache: Dict[str, InheritanceState] = {}

    def resolve(doc: Any, stack: Tuple[str, ...]) -> InheritanceState:
        doc_key = _doc_id(doc)
        if doc_key in cache:
            return cache[doc_key]

        filename = doc.path.name.lower()
        if filename in stack:
            start = stack.index(filename)
            cycle = stack[start:] + (filename,)
            state = InheritanceState("cycle", (doc,), target=filename, cycle=cycle)
            cache[doc_key] = state
            return state

        ref = canonical_base_reference(doc)
        if ref is None:
            state = InheritanceState("complete", (doc,))
            cache[doc_key] = state
            return state

        parent_name = ref.parent
        if parent_name == filename:
            cycle = (filename, filename)
            state = InheritanceState("cycle", (doc,), target=parent_name, cycle=cycle)
            cache[doc_key] = state
            return state

        if parent_name in duplicates:
            state = InheritanceState("ambiguous", (doc,), target=parent_name)
            cache[doc_key] = state
            return state

        parent = unique.get(parent_name)
        if parent is None:
            status = "opaque" if parent_name in known else "missing"
            state = InheritanceState(status, (doc,), target=parent_name)
            cache[doc_key] = state
            return state

        parent_state = resolve(parent, stack + (filename,))
        chain = (doc,) + parent_state.chain
        if parent_state.status == "complete":
            state = InheritanceState("complete", chain)
        else:
            state = InheritanceState(
                parent_state.status,
                chain,
                target=parent_state.target or parent_name,
                cycle=parent_state.cycle,
            )
        cache[doc_key] = state
        return state

    for doc in documents:
        resolve(doc, ())

    return InheritanceGraph(states=cache, duplicates=duplicates)


def merge_effective_sections(state: InheritanceState) -> tuple[Dict[str, list], Dict[str, str]]:
    """Merge the known local chain parent-first, then child overrides by key.

    The result is useful even for opaque chains for positive/local diagnostics,
    but callers must only infer *absence* when `state.complete` is true.
    """
    merged: Dict[str, Dict[str, tuple]] = {}
    section_names: Dict[str, str] = {}

    # state.chain is child -> parent; load parent first so child wins.
    for doc in reversed(state.chain):
        for section_lower, entries in doc.sections.items():
            section_names[section_lower] = doc.original_sections.get(section_lower, section_lower)
            bucket = merged.setdefault(section_lower, {})
            for key, value, line in entries:
                bucket[key.lower()] = (key, value, line)

    sections: Dict[str, list] = {}
    for section_lower, entries in merged.items():
        sections[section_lower] = [
            (key, value, line)
            for key, value, line in entries.values()
        ]
    return sections, section_names

# ODF validation schema

The ODF checker is deliberately **loader-oriented**, not a generic INI linter.

`odf_schema.py` contains curated, evidence-backed Redux loader contracts. `odf_validator.py` evaluates the physical ODF declarations against those contracts. Research output may contain far more discovered sections/keys than the curated validator exposes; that separation is intentional.

## Evidence policy

A hard validator rule should only be added when its behavior is supported strongly enough to justify user-facing diagnostics. Preferred evidence is:

1. Redux executable/decomp loader behavior,
2. code behavior corroborated by stock Redux ODFs,
3. a reproducible runtime failure tied back to the loader path.

Stock-only observations are useful research evidence but should not automatically become hard failures. `inferred`, hash-only, or name-unresolved findings are parse/report research data only until separately verified.

The current schema is intentionally incomplete. Unknown sections and keys are **not** automatically treated as invalid. That would create unacceptable false positives for custom/legacy content.

## Structured provenance

Schema version 3 adds `EvidenceRef` records to curated rules. An evidence record can carry:

- evidence kind,
- confidence,
- repository and path,
- recovered function/symbol,
- executable address,
- source commit,
- representative stock file,
- runtime reproduction identifier, and
- a concise statement of what the evidence proves.

Confidence vocabulary is deliberately small:

| Confidence | Meaning |
| --- | --- |
| `confirmed-code` | Behavior directly recovered from loader/decomp code. |
| `code+stock` | Code behavior corroborated by stock content or runtime reproduction. |
| `stock-only` | Observed in stock content but not yet code-proven. |
| `inferred` | Hypothesis/research lead; never sufficient by itself for a hard rule. |

Research corpus entries should be reviewed before promotion into `LOADER_RULES`. The validator must not turn "found in the mining JSON" into "invalid ODF" automatically.

## Current loader rules

| Rule ID | Context | Redux section | Legacy/problem section | Severity |
| --- | --- | --- | --- | --- |
| `game-object-root` | object root dispatch | `GameObjectClass` | `GameObject` | Error |
| `flare-mine` | `classLabel=flare` + `MineClass` | `FlareMineClass` | `FlareBuildingClass` | Critical |
| `magnet-mine` | `classLabel=magnet` + `OrdnanceClass` + `MineClass` | `MagnetMineClass` | `MagnetClass` | Error |
| `scavenger` | `classLabel=scavenger` + `CraftClass` | `ScavengerClass` | `ScavengerCraftClass` | Error |
| `flame-puff` | `classLabel=flamepuff` + `OrdnanceClass` | `FlamePuffClass` | `flameClass` | Error |

Context is important. Similar section names can be used in unrelated legacy content, so the scanner only applies migration rules when the surrounding loader path is proven.

## Flare crash provenance

`flare-mine` has a concrete recovered failure chain:

1. `FlareMineClass::Load` at `0x004D2B10` resolves `payloadName` into the payload `OrdnanceClass` pointer.
2. `FlareMine::Update(float)` at `0x004D2E90` follows that payload pointer when the mine fires.
3. `OrdnanceClass::Build` at `0x00586FF0` reaches an unguarded dereference when the payload class is null.
4. The confirmed AbsoZero access violation occurs at `0x00586FFC`, reading `+0x38` through a null class pointer.

`[FlareBuildingClass]` has no loader reader in the mined code corpus, so putting `payloadName` there does not initialize the field consumed by the flare firing path. A canonical `[FlareMineClass]` with no `payloadName` is likewise Critical.

The scanner deliberately does **not** infer that every flare lacking a physical `[FlareMineClass]` must crash. That stronger absence claim depends on prototype/default semantics and is not made without direct proof.

## `baseName` is not ODF file inheritance

A previous scanner revision treated canonical `baseName` as an ODF-to-ODF inheritance edge. That model was removed after loader mining showed:

- `baseName` has a real code reader,
- but that reader does **not** load another ODF and merge its sections or keys,
- defaults instead come from the engine's prototype/class chain.

Therefore the validator does not:

- merge a `baseName` target into the child ODF,
- inherit `classLabel` or loader sections from another file,
- treat a missing `baseName` target as a dependency error,
- construct file-level cycles from `baseName`, or
- suppress a physical missing key because another ODF happens to have the referenced filename.

Lowercase `basename` also remains distinct from canonical `baseName`; the scanner does not invent global case-insensitivity rules.

## Key spelling and dead-field policy

Key spelling is only judged when code evidence identifies the consumed key. Current examples include:

- `MagnetMineClass.triggerDelay` is code-read; `triggetDelay` has no reader.
- `FlamePuffClass.frameDelay` is code-read; `flameDelay` has no recovered reader despite appearing in stock content.

This is exactly why stock files are corroboration rather than absolute truth: shipped content can contain dead or misspelled fields too.

## ODF references

The schema currently validates these ODF-valued fields against the combined local + stock filename namespace:

- `FlareMineClass.payloadName`
- `OrdnanceClass.xplGround`
- `OrdnanceClass.xplVehicle`
- `OrdnanceClass.xplBuilding`

Near-miss names receive a suggested replacement, which catches cases such as `xmlasbld` vs `xlasbld`.

Reference checking is a filename/dependency check only. It does not imply `baseName` file inheritance.

## Research corpus boundary

The loader-mining corpus is intentionally broader than the validator. It may contain:

- keyed loaders,
- zero-key chain links,
- hash-only sections,
- name-unresolved keys,
- stock-only anomalies,
- code-proven crash risks,
- guarded conditions that are explicitly safe.

The validator should promote only the subset that has a clear, defensible user-facing consequence. Guarded code paths are recorded specifically to avoid false-positive "crash risk" rules.

## Regression corpus

The test suite contains minimized versions of the AbsoZero failure family plus false-positive controls. It verifies:

- flare legacy-section and missing-payload crash findings,
- magnet mine section and `triggerDelay` spelling,
- scavenger section naming,
- flame-puff legacy fields and `frameDelay` spelling,
- legacy `GameObject` root dispatch,
- ODF reference typo detection,
- ZIP validation without extraction,
- no fabricated `baseName` parent merging, cycles, or missing-parent diagnostics,
- and concrete provenance addresses for the flare crash chain.

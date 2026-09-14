# ODF validation schema

The ODF checker is deliberately **loader-oriented**, not a generic INI linter.

`odf_schema.py` describes evidence-backed Redux loader contracts. `odf_validator.py` parses community ODFs, determines the relevant loader path from `classLabel` plus base sections, and evaluates the matching rules. This keeps section/key knowledge separate from validation mechanics and makes every finding traceable to a stable rule ID.

## Evidence policy

A rule should only be added when it is supported by at least one of:

1. Redux executable/decomp loader behavior,
2. a stock Redux ODF contract, or
3. a reproducible runtime failure.

The current schema is intentionally incomplete. Unknown sections and keys are **not** automatically treated as invalid. That would create unacceptable false positives for custom/legacy content.

## Initial loader rules

| Rule ID | Context | Redux section | Legacy/problem section | Severity |
| --- | --- | --- | --- | --- |
| `game-object-root` | object root | `GameObjectClass` | `GameObject` | Error |
| `flare-mine` | `classLabel=flare` + `MineClass` | `FlareMineClass` | `FlareBuildingClass` | Critical |
| `magnet-mine` | `classLabel=magnet` + `OrdnanceClass` + `MineClass` | `MagnetMineClass` | `MagnetClass` | Error |
| `scavenger` | `classLabel=scavenger` + `CraftClass` | `ScavengerClass` | `ScavengerCraftClass` | Error |
| `flame-puff` | `classLabel=flamepuff` + `OrdnanceClass` | `FlamePuffClass` | `flameClass` | Error |

The context is important. `[MagnetClass]` is not globally invalid: building magnets use a different path and must not be rewritten as magnet mines. Likewise, `[flameClass]` is only diagnosed as a `FlamePuffClass` migration when the ODF itself identifies the flame-puff loader path.

## Crash-risk semantics

`flare-mine` is currently the strongest semantic rule. A legacy `[FlareBuildingClass]` can leave the native flare payload pointer null because Redux never consumes that section. `FlareMine::Update()` later dereferences the payload class, producing the confirmed access violation. A canonical `[FlareMineClass]` with an empty/missing `payloadName` is therefore also Critical.

## ODF references

The schema currently validates these ODF-valued fields against the combined local + stock namespace:

- `FlareMineClass.payloadName`
- `OrdnanceClass.xplGround`
- `OrdnanceClass.xplVehicle`
- `OrdnanceClass.xplBuilding`

Near-miss names receive a suggested replacement, which catches cases such as `xmlasbld` vs `xlasbld`.

## Inheritance boundary

The checker does **not yet resolve `baseName` inheritance**. Because a child ODF may inherit a class-specific section from its parent, absence of a section alone is not currently an error. Rules only diagnose a canonical/known-legacy section that is actually present in the file, except where the canonical section itself is present and a required field is missing.

Inheritance resolution is the next major schema milestone. Once implemented, the validator can safely reason about effective values across a complete ODF chain instead of only local declarations.

## Regression corpus

The test suite contains minimized versions of the failure family recovered from the AbsoZero mission: three flare crash definitions, magnet-mine legacy sections and misspelled `triggetDelay`, scavenger section mismatches, the legacy GameObject root, flame-puff fields, the `xmlasbld` typo, plus a building magnet negative control.

ZIP validation is also covered so packaged mods can be checked without extraction.

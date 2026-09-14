# ODF validation schema

The ODF checker is deliberately **loader-oriented**, not a generic INI linter.

`odf_schema.py` describes evidence-backed Redux loader contracts. `odf_inheritance.py` resolves the inheritance relationships that can be proven from the scanned package, and `odf_validator.py` evaluates the resulting effective ODF state. This keeps loader knowledge, inheritance mechanics, and diagnostics separate and gives every finding a stable rule ID.

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

`flare-mine` is currently the strongest semantic rule. A legacy `[FlareBuildingClass]` can leave the native flare payload pointer null because Redux never consumes that section. `FlareMine::Update()` later dereferences the payload class, producing the confirmed access violation. A canonical `[FlareMineClass]` with an empty/missing effective `payloadName` is therefore also Critical.

When the scanner has a **complete local inheritance chain**, it can now also prove the stronger absence case: a `classLabel=flare` / `MineClass` object with no effective `[FlareMineClass]` is Critical because no resolved loader section can initialize the payload at all.

## ODF references

The schema currently validates these ODF-valued fields against the combined local + stock namespace:

- `FlareMineClass.payloadName`
- `OrdnanceClass.xplGround`
- `OrdnanceClass.xplVehicle`
- `OrdnanceClass.xplBuilding`

Near-miss names receive a suggested replacement, which catches cases such as `xmlasbld` vs `xlasbld`.

## `baseName` inheritance

Inheritance resolution is intentionally conservative.

- Only the exact canonical key **`baseName`** is followed. Lowercase `basename` is not promoted into inheritance semantics.
- Canonical roots currently checked for `baseName` are `GameObjectClass`, `OrdnanceClass`, and `WeaponClass`.
- Local parent ODFs are resolved recursively, case-insensitively by filename, and their sections/keys are merged parent-first so child values override parent values.
- `classLabel`, class sections, and required keys can therefore be inherited from a local parent.
- Self references and multi-file cycles are Errors.
- Missing custom parents are Errors.
- Duplicate ODF basenames that make a parent ambiguous are Errors.
- A parent found only in the known stock ODF namespace is **opaque**, not missing. The scanner knows the stock filename exists but does not pretend to know that parent ODF's contents.

That last rule is important. An opaque stock parent prevents absence-based claims. For example, a child flare that inherits a stock ODF is not called broken merely because the package itself lacks `[FlareMineClass]`; the stock parent may provide it. Positive local errors such as a legacy `[MagnetClass]` are still reported.

## Effective-value policy

The scanner distinguishes two classes of findings:

1. **Positive/local evidence** — a bad section, misspelled key, explicit blank required field, or bad reference physically present in the file. These can be reported even when the parent is opaque.
2. **Absence/effective-state evidence** — a missing loader section or inherited required field. These are reported only when the entire inheritance chain is locally known.

This prevents the schema from turning incomplete package knowledge into false positives.

## Regression corpus

The test suite contains minimized versions of the failure family recovered from the AbsoZero mission: three flare crash definitions, magnet-mine legacy sections and misspelled `triggetDelay`, scavenger section mismatches, the legacy GameObject root, flame-puff fields, the `xmlasbld` typo, plus a building magnet negative control.

Inheritance tests additionally cover:

- local parent supplying a class label, loader section, and `payloadName`,
- child sections inheriting missing keys from their local parent,
- explicit child values overriding inherited values,
- complete chains with no `FlareMineClass`,
- opaque stock parents,
- missing custom parents,
- exact self-reference and multi-file cycles,
- lowercase `basename` remaining inert, and
- referenced-only validation still resolving unselected local parents.

ZIP validation is also covered so packaged mods can be checked without extraction.

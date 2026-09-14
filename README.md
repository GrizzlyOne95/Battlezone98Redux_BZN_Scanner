# Battlezone98Redux BZN Scanner

A Battlezone 98 Redux mission preflight utility. It scans ASCII or binary `.BZN` files for referenced ODFs, classifies them as stock/custom, checks custom dependencies, and validates local or packaged ODF files against known Redux loader behavior.

<img width="802" height="632" alt="BZN Scanner" src="https://github.com/user-attachments/assets/5fc44ce6-5d20-45b0-8089-e2d475c86ea7" />

## Scan modes

The integrated GUI supports three entry points:

- **Load BZN** - scan mission ODF dependencies and validate ODFs beside the BZN.
- **Scan ODF Folder** - validate every ODF in a mod/work folder without requiring a BZN.
- **Scan ZIP** - validate ODFs directly inside a packaged ZIP without extracting it first.

## BZN Dependencies

- Reads both ASCII and binary Redux BZN files.
- Extracts referenced ODF names from mission data.
- Separates stock and custom ODFs.
- Checks whether required custom ODF files are present beside the BZN.
- Handles local ODF filename matching case-insensitively, matching normal Windows mod-folder behavior.

## ODF Validation

The **ODF Validation** tab is read-only: the scanner reports findings and suggested fixes but never rewrites mission files. Findings include severity, file, line number where available, section/key, stable rule ID, suggested fix, and the evidence/source used for the rule.

Validation is driven by `odf_schema.py` rather than hard-coding every special case into the parser. Rules combine `classLabel` with the class sections physically present in the ODF so the checker can distinguish loader paths that reuse similar legacy names.

### Important: `baseName` is not ODF file inheritance

Earlier versions of the scanner treated canonical `baseName` as an ODF-to-ODF inheritance edge and merged parent files before validation. Recovered loader evidence disproves that model: Redux has a reader for `baseName`, but it does **not** load another ODF and merge its sections/keys. Defaults come from the engine's prototype/class chain instead.

The scanner therefore evaluates each ODF's physical loader sections independently. It does not synthesize class labels, loader sections, keys, missing-parent errors, or cycles from `baseName` references.

The initial evidence-backed schema covers the failure family exposed by the legacy **AbsoZero** mission:

- **CRITICAL:** `classLabel = "flare"` using `[FlareBuildingClass]` instead of Redux `[FlareMineClass]`. The legacy section has no loader reader; `payloadName` can remain null and the flare firing path can fault while building the payload ordnance.
- **CRITICAL:** canonical `[FlareMineClass]` with no `payloadName`.
- **ERROR:** legacy `[GameObject]` where Redux dispatch expects `[GameObjectClass]`.
- **ERROR:** magnet mine/ordnance ODFs using `[MagnetClass]` instead of `[MagnetMineClass]`.
- **ERROR:** magnet mine `triggetDelay` typo instead of `triggerDelay`.
- **ERROR:** scavenger objects using `[ScavengerCraftClass]` instead of `[ScavengerClass]`.
- **ERROR/WARNING:** `classLabel = "flamepuff"` using legacy `[flameClass]` and unsupported fields such as `flameLength`, `variance`, and `shotColor`.
- **WARNING:** `flameDelay` in `[FlamePuffClass]`; recovered code reads `frameDelay` instead.
- **WARNING:** missing/misspelled `xplGround`, `xplVehicle`, and `xplBuilding` ODF references, checked against both local and stock ODF names. This catches errors such as `xmlasbld` vs `xlasbld` without flagging valid stock assets as missing.

Rules are intentionally context-sensitive. For example, the scanner does **not** blindly rename every `[MagnetClass]` or `[flameClass]`; those names are diagnosed only when the surrounding `classLabel` and class sections identify a proven loader path.

## Provenance model

`odf_schema.py` now supports structured `EvidenceRef` records in addition to the short human-readable source string. Provenance can identify the evidence kind, confidence, repository/path, recovered symbol/address, stock example, runtime reproduction, and source commit.

Current confidence vocabulary:

- `confirmed-code` - loader/decomp behavior directly recovered from code.
- `code+stock` - code behavior corroborated by stock content or runtime reproduction.
- `stock-only` - observed in stock content but not yet proven by code.
- `inferred` - hypothesis/research lead only.

Research output is **not automatically validator policy**. Inferred, hash-only, unresolved, and stock-only discoveries remain parse/report research data until reviewed. Hard diagnostics should be promoted only when the engine behavior and consequence are sufficiently proven.

The flare crash rule already carries a concrete recovered chain:

`FlareMineClass::Load 0x004D2B10 -> FlareMine::Update 0x004D2E90 -> OrdnanceClass::Build 0x00586FF0`

with the confirmed null dereference at `0x00586FFC`.

See [`docs/ODF_VALIDATION_SCHEMA.md`](docs/ODF_VALIDATION_SCHEMA.md) for the schema contract and evidence policy.

## Command-line ODF validation

The same validator can be used without the GUI:

```bash
python odf_validator.py path/to/mod-folder
python odf_validator.py path/to/mod.zip
python odf_validator.py path/to/file.odf
python odf_validator.py path/to/mod.zip --json
```

Exit codes are suitable for automation: `0` for warnings/no findings, `1` when errors are present, and `2` when a Critical crash-risk finding is present.

## Rule policy

ODF checks should be traceable to at least one of:

1. Redux loader/decomp behavior,
2. a stock Redux ODF contract, or
3. a reproducible runtime failure.

The goal is a codebase-rooted ODF preflight schema rather than a generic INI spell-checker. Unknown sections and keys are not automatically rejected while the schema is incomplete.

## Development

Run the regression suite with:

```bash
python -m unittest discover -s tests -v
```

The test suite includes minimized AbsoZero regression cases, false-positive controls, ZIP scanning, explicit regressions preventing `baseName` file merging, and provenance checks for code-backed crash rules. The release workflow runs the tests before packaging the integrated `scanner_app.py` front end for Windows, Linux, and macOS.

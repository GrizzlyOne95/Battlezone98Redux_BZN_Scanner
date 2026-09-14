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

Validation is driven by `odf_schema.py` rather than hard-coding every special case into the parser. Rules combine `classLabel` with the base class sections present in the ODF, which lets the checker distinguish loader paths that reuse similar legacy names.

The validator also resolves **local canonical `baseName` inheritance**. It merges local parent chains parent-first, lets child values override inherited values, detects missing/cyclic/ambiguous parents, and can reason about inherited `classLabel`, class sections, and required fields. Known stock parents are deliberately treated as opaque: the scanner knows the parent exists but does not guess its contents. Lowercase `basename` remains inert rather than being silently promoted to `baseName`.

The initial evidence-backed schema covers the failure family exposed by the legacy **AbsoZero** mission:

- **CRITICAL:** `classLabel = "flare"` using `[FlareBuildingClass]` instead of Redux `[FlareMineClass]`. This can leave the payload class null and crash `FlareMine::Update()` when the flare fires.
- **CRITICAL:** canonical/effective `[FlareMineClass]` with no `payloadName`.
- **CRITICAL:** a fully resolved local flare chain with no effective `[FlareMineClass]` at all.
- **ERROR:** legacy `[GameObject]` where Redux expects `[GameObjectClass]`, with migration guidance for canonical `baseName`.
- **ERROR:** magnet mine/ordnance ODFs using `[MagnetClass]` instead of `[MagnetMineClass]`.
- **ERROR:** magnet mine `triggetDelay` typo instead of `triggerDelay`.
- **ERROR:** scavenger objects using `[ScavengerCraftClass]` instead of `[ScavengerClass]`.
- **ERROR/WARNING:** `classLabel = "flamepuff"` using legacy `[flameClass]` and fields such as `flameLength`, `variance`, and `shotColor` instead of the Redux `FlamePuffClass` model.
- **WARNING:** missing/misspelled `xplGround`, `xplVehicle`, and `xplBuilding` ODF references, checked against both local and stock ODF names. This catches errors such as `xmlasbld` vs `xlasbld` without flagging valid stock assets as missing.

Rules are intentionally context-sensitive. For example, the scanner does **not** blindly rename every `[MagnetClass]` or `[flameClass]`; those labels are only diagnosed when the surrounding `classLabel` and base sections identify the specific Redux loader path.

See [`docs/ODF_VALIDATION_SCHEMA.md`](docs/ODF_VALIDATION_SCHEMA.md) for schema design, evidence requirements, and inheritance semantics.

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

The goal is a codebase-rooted ODF preflight schema rather than a generic INI spell-checker. Unknown sections/keys are not automatically rejected while the schema is incomplete, and effective-state claims are withheld when an inheritance parent is opaque.

## Development

Run the regression suite with:

```bash
python -m unittest discover -s tests -v
```

The test suite includes minimized AbsoZero regression cases, false-positive controls, ZIP scanning, and local inheritance/cycle/override coverage. The release workflow runs the tests before packaging the integrated `scanner_app.py` front end for Windows, Linux, and macOS.

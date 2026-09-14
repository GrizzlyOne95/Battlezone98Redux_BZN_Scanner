# Battlezone98Redux BZN Scanner

A Battlezone 98 Redux mission preflight utility. It scans ASCII or binary `.BZN` files for referenced ODFs, classifies them as stock/custom, checks custom dependencies, and now validates local ODF files against known Redux loader behavior.

<img width="802" height="632" alt="BZN Scanner" src="https://github.com/user-attachments/assets/5fc44ce6-5d20-45b0-8089-e2d475c86ea7" />

## BZN Dependencies

- Reads both ASCII and binary Redux BZN files.
- Extracts referenced ODF names from mission data.
- Separates stock and custom ODFs.
- Checks whether required custom ODF files are present beside the BZN.
- Handles local ODF filename matching case-insensitively, matching normal Windows mod-folder behavior.

## ODF Validation

Loading a BZN also scans the ODFs in the same directory and opens an **ODF Validation** tab. Validation is read-only: the scanner reports findings and suggested fixes but never rewrites mission files.

The initial evidence-backed rule pack covers the failure family exposed by the legacy **AbsoZero** mission:

- **CRITICAL:** `classLabel = "flare"` using `[FlareBuildingClass]` instead of Redux `[FlareMineClass]`. This can leave the payload class null and crash `FlareMine::Update()` when the flare fires.
- **CRITICAL:** `[FlareMineClass]` with no `payloadName`.
- **ERROR:** legacy `[GameObject]` where Redux expects `[GameObjectClass]`, with migration guidance for canonical `baseName`.
- **ERROR:** magnet mine/ordnance ODFs using `[MagnetClass]` instead of `[MagnetMineClass]`.
- **ERROR:** magnet mine `triggetDelay` typo instead of `triggerDelay`.
- **ERROR:** scavenger objects using `[ScavengerCraftClass]` instead of `[ScavengerClass]`.
- **ERROR/WARNING:** `classLabel = "flamepuff"` using legacy `[flameClass]` and fields such as `flameLength`, `variance`, and `shotColor` instead of the Redux `FlamePuffClass` model.
- **WARNING:** missing/misspelled `xplGround`, `xplVehicle`, and `xplBuilding` ODF references, checked against both local and stock ODF names. This catches errors such as `xmlasbld` vs `xlasbld` without flagging valid stock assets as missing.

Rules are intentionally context-sensitive. For example, the scanner does **not** blindly rename every `[MagnetClass]` or `[flameClass]`; those labels are only diagnosed when the surrounding `classLabel` and class sections identify the specific Redux loader path.

## Rule policy

ODF checks should be traceable to at least one of:

1. Redux loader/decomp behavior,
2. a stock Redux ODF contract, or
3. a reproducible runtime failure.

The goal is to grow this into a codebase-rooted ODF preflight schema rather than a generic INI spell-checker.

## Development

Run the regression suite with:

```bash
python -m unittest discover -s tests -v
```

The release workflow runs the same tests before packaging the integrated `scanner_app.py` front end for Windows, Linux, and macOS.

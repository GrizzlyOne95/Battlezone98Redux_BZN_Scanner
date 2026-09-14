import tempfile
import unittest
from pathlib import Path

from odf_validator import validate_directory


class ODFValidatorTests(unittest.TestCase):
    def write_odf(self, root: Path, name: str, text: str) -> None:
        (root / name).write_text(text, encoding="latin-1", newline="\r\n")

    def test_flarebuilding_is_crash_risk(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "badflare.odf", """
[GameObjectClass]
classLabel = "flare"
[MineClass]
lifeSpan = 1e10
[FlareBuildingClass]
payloadName = "payload"
shotDelay = 0.10
""")
            self.write_odf(root, "payload.odf", """
[OrdnanceClass]
classLabel = "explosion"
""")
            issues = validate_directory(root)
            critical = [i for i in issues if i.severity == "CRITICAL"]
            self.assertEqual(1, len(critical))
            self.assertIn("FlareMineClass", critical[0].suggestion)

    def test_valid_flaremine_payload_does_not_raise_critical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "flare.odf", """
[GameObjectClass]
classLabel = "flare"
[MineClass]
lifeSpan = 1e10
[FlareMineClass]
payloadName = "payload"
""")
            self.write_odf(root, "payload.odf", "[OrdnanceClass]\nclassLabel = \"explosion\"\n")
            issues = validate_directory(root)
            self.assertFalse(any(i.severity == "CRITICAL" for i in issues))

    def test_magnet_mine_legacy_section_and_typo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "magmine.odf", """
[OrdnanceClass]
classLabel = "magnet"
[MineClass]
lifeSpan = 120
[MagnetClass]
triggetDelay = 0.1
fieldRadius = 30
""")
            issues = validate_directory(root)
            self.assertTrue(any("MagnetMineClass" in i.suggestion for i in issues))
            self.assertTrue(any(i.key == "triggetDelay" and "triggerDelay" in i.suggestion for i in issues))

    def test_building_magnet_is_not_reclassified_as_magnet_mine(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "buildingmagnet.odf", """
[GameObjectClass]
classLabel = "magnet"
[BuildingClass]
lifeSpan = 15
[MagnetClass]
triggetDelay = 0.0
fieldRadius = 120
""")
            issues = validate_directory(root)
            self.assertFalse(any("MagnetMineClass" in i.suggestion for i in issues))

    def test_scavenger_legacy_section(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "scav.odf", """
[GameObjectClass]
classLabel = "scavenger"
[CraftClass]
[HoverCraftClass]
[ScavengerCraftClass]
maxScrap = 4
""")
            issues = validate_directory(root)
            self.assertTrue(any("ScavengerClass" in i.suggestion for i in issues))

    def test_flamepuff_and_stock_explosion_typo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "flame.odf", """
[OrdnanceClass]
classLabel = "flamepuff"
xplGround = "xlasgnd"
xplVehicle = "xlascar"
xplBuilding = "xmlasbld"
[flameClass]
flameTexture = "rpuff.5"
shotColor = 124
variance = 80
flameLength = 10
flameRadius = 40
""")
            stock = {"xlasgnd.odf", "xlascar.odf", "xlasbld.odf"}
            issues = validate_directory(root, known_odfs=stock)
            self.assertTrue(any("FlamePuffClass" in i.suggestion for i in issues))
            typo = [i for i in issues if i.key == "xplbuilding"]
            self.assertEqual(1, len(typo))
            self.assertIn("xlasbld.odf", typo[0].suggestion)

    def test_switcher_flameclass_is_not_reclassified(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "switcher.odf", """
[OrdnanceClass]
classLabel = "switcher"
[TeamSwitcherClass]
switchTime = 1E6
[flameClass]
segmentRadius = 10
segmentLength = 40
""")
            issues = validate_directory(root)
            self.assertFalse(any("FlamePuffClass" in i.suggestion for i in issues))

    def test_gameobject_legacy_section(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "tank.odf", """
[GameObject]
basename = "bvltnk"
classLabel = "wingman"
[CraftClass]
[HoverCraftClass]
""")
            issues = validate_directory(root)
            self.assertTrue(any("GameObjectClass" in i.suggestion for i in issues))
            self.assertTrue(any(i.key == "basename" for i in issues))


if __name__ == "__main__":
    unittest.main()

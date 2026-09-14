import tempfile
import unittest
from pathlib import Path

from odf_validator import validate_directory


class ODFInheritanceTests(unittest.TestCase):
    def write_odf(self, root: Path, name: str, text: str) -> None:
        (root / name).write_text(text, encoding="latin-1", newline="\r\n")

    def test_local_parent_supplies_flare_loader_and_payload(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "parent.odf", """
[GameObjectClass]
classLabel = "flare"
[MineClass]
lifeSpan = 10
[FlareMineClass]
payloadName = "payload"
shotDelay = 0.1
""")
            self.write_odf(root, "child.odf", """
[GameObjectClass]
baseName = "parent"
unitName = "Inherited Flare"
""")
            self.write_odf(root, "payload.odf", "[OrdnanceClass]\nclassLabel = \"explosion\"\n")

            issues = validate_directory(root, filenames=["child.odf"])
            self.assertFalse(any(i.severity == "CRITICAL" for i in issues))
            self.assertFalse(any(i.rule_id.startswith("inheritance-") for i in issues))

    def test_local_parent_key_is_inherited_when_child_has_same_section(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "parent.odf", """
[GameObjectClass]
classLabel = "flare"
[MineClass]
lifeSpan = 10
[FlareMineClass]
payloadName = "payload"
shotDelay = 0.1
""")
            self.write_odf(root, "child.odf", """
[GameObjectClass]
baseName = "parent"
classLabel = "flare"
[MineClass]
lifeSpan = 20
[FlareMineClass]
shotDelay = 0.2
""")
            self.write_odf(root, "payload.odf", "[OrdnanceClass]\nclassLabel = \"explosion\"\n")

            issues = validate_directory(root, filenames=["child.odf"])
            self.assertFalse(any(i.key == "payloadName" and i.severity == "CRITICAL" for i in issues))

    def test_explicit_blank_child_payload_overrides_parent_and_is_critical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "parent.odf", """
[GameObjectClass]
classLabel = "flare"
[MineClass]
[FlareMineClass]
payloadName = "payload"
""")
            self.write_odf(root, "child.odf", """
[GameObjectClass]
baseName = "parent"
classLabel = "flare"
[MineClass]
[FlareMineClass]
payloadName = ""
""")
            self.write_odf(root, "payload.odf", "[OrdnanceClass]\nclassLabel = \"explosion\"\n")

            issues = validate_directory(root, filenames=["child.odf"])
            self.assertTrue(any(i.key == "payloadName" and i.severity == "CRITICAL" for i in issues))

    def test_complete_chain_without_flaremineclass_is_critical(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "parent.odf", """
[GameObjectClass]
classLabel = "flare"
[MineClass]
lifeSpan = 10
""")
            self.write_odf(root, "child.odf", """
[GameObjectClass]
baseName = "parent"
""")

            issues = validate_directory(root, filenames=["child.odf"])
            self.assertTrue(any(
                i.rule_id == "flare-mine"
                and i.section == "FlareMineClass"
                and i.severity == "CRITICAL"
                for i in issues
            ))

    def test_known_stock_parent_is_opaque_not_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "child.odf", """
[GameObjectClass]
baseName = "stockflare"
classLabel = "flare"
[MineClass]
lifeSpan = 10
""")

            issues = validate_directory(root, known_odfs={"stockflare.odf"})
            self.assertFalse(any(i.rule_id == "inheritance-missing-parent" for i in issues))
            self.assertFalse(any(
                i.rule_id == "flare-mine"
                and i.section == "FlareMineClass"
                and i.severity == "CRITICAL"
                for i in issues
            ))

    def test_missing_custom_parent_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "child.odf", """
[GameObjectClass]
baseName = "doesnotexist"
classLabel = "wingman"
""")
            issues = validate_directory(root)
            missing = [i for i in issues if i.rule_id == "inheritance-missing-parent"]
            self.assertEqual(1, len(missing))
            self.assertEqual("ERROR", missing[0].severity)
            self.assertEqual(3, missing[0].line)

    def test_exact_self_reference_is_cycle_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "self.odf", """
[GameObjectClass]
baseName = "self"
classLabel = "wingman"
""")
            issues = validate_directory(root)
            self.assertTrue(any(i.rule_id == "inheritance-cycle" for i in issues))

    def test_lowercase_basename_self_reference_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "self.odf", """
[GameObjectClass]
basename = "self"
classLabel = "wingman"
""")
            issues = validate_directory(root)
            self.assertFalse(any(i.rule_id.startswith("inheritance-") for i in issues))

    def test_two_file_cycle_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "a.odf", """
[GameObjectClass]
baseName = "b"
classLabel = "wingman"
""")
            self.write_odf(root, "b.odf", """
[GameObjectClass]
baseName = "a"
classLabel = "wingman"
""")
            issues = validate_directory(root)
            cycle_files = {i.filename for i in issues if i.rule_id == "inheritance-cycle"}
            self.assertEqual({"a.odf", "b.odf"}, cycle_files)

    def test_referenced_only_still_parses_unselected_local_parent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write_odf(root, "parent.odf", """
[GameObjectClass]
classLabel = "flare"
[MineClass]
[FlareMineClass]
payloadName = "payload"
""")
            self.write_odf(root, "child.odf", """
[GameObjectClass]
baseName = "parent"
""")
            self.write_odf(root, "payload.odf", "[OrdnanceClass]\nclassLabel = \"explosion\"\n")

            issues = validate_directory(root, filenames=["child.odf"])
            self.assertFalse(any(i.severity in {"CRITICAL", "ERROR"} for i in issues))


if __name__ == "__main__":
    unittest.main()

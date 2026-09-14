import tempfile
import unittest
import zipfile
from pathlib import Path

from odf_validator import validate_directory, validate_zip


class ODFInheritanceEdgeTests(unittest.TestCase):
    def test_ordnanceclass_basename_is_an_inheritance_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "child.odf").write_text(
                '[OrdnanceClass]\nbaseName = "missingmag"\nclassLabel = "magnet"\n[MineClass]\n',
                encoding="latin-1",
            )
            issues = validate_directory(root)
            self.assertTrue(any(
                i.rule_id == "inheritance-missing-parent"
                and i.section == "OrdnanceClass"
                for i in issues
            ))

    def test_weaponclass_basename_is_an_inheritance_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "child.odf").write_text(
                '[WeaponClass]\nbaseName = "missingweapon"\n',
                encoding="latin-1",
            )
            issues = validate_directory(root)
            self.assertTrue(any(
                i.rule_id == "inheritance-missing-parent"
                and i.section == "WeaponClass"
                for i in issues
            ))

    def test_duplicate_zip_parent_basename_makes_reference_ambiguous(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "duplicate-parent.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("one/parent.odf", '[GameObjectClass]\nclassLabel="wingman"\n')
                zf.writestr("two/parent.odf", '[GameObjectClass]\nclassLabel="wingman"\n')
                zf.writestr(
                    "child.odf",
                    '[GameObjectClass]\nbaseName="parent"\nclassLabel="wingman"\n',
                )
            issues = validate_zip(archive)
            self.assertTrue(any(
                i.filename == "child.odf"
                and i.rule_id == "inheritance-ambiguous-parent"
                for i in issues
            ))


if __name__ == "__main__":
    unittest.main()

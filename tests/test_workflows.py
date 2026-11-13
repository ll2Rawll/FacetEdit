import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from facetedit import nbt
from facetedit.blocks import AIR, Block
from facetedit.model import Document, Selection
from facetedit.region import Region
from facetedit.settings import Settings
from facetedit.structures import export_structure, import_structure, import_mcstructure, load_project, save_project
from facetedit.world import SampleWorld, open_world, file_hash
from tests.fixtures import bedrock_world, java_world


def hashes(path):
    return {str(f.relative_to(path)): file_hash(f) for f in Path(path).rglob("*") if f.is_file()}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_java_edit_undo_export_reopen_source_unchanged(self):
        source = java_world(self.path / "java")
        original = hashes(source)
        doc = Document(open_world(source))
        self.assertEqual(doc.world.name, "Test meadow")
        doc.selection = Selection((1, 2, 3), (2, 3, 4))
        self.assertEqual(doc.fill(Block("gold_block")), 8)
        doc.undo()
        self.assertEqual(doc.get(1, 2, 3), Block("stone"))
        doc.redo()
        output = self.path / "edited"
        doc.world.export(output, doc.edits)
        reopened = open_world(output)
        self.assertEqual(reopened.get_block(1, 2, 3), Block("gold_block"))
        self.assertEqual(reopened.get_block(0, 2, 3), Block("stone"))
        self.assertEqual(hashes(source), original)
        self.assertEqual((output / "extra.dat").read_bytes(), b"unrelated preserved bytes")
        raw = Region.read(output / "region/r.0.0.mca").get(0, 0)
        _, root = nbt.loads(raw)
        self.assertEqual(nbt.get(root, "CustomUnknown"), "preserve me")
        self.assertEqual(nbt.get(root, "InhabitedTime"), 12345)
        self.assertEqual(nbt.get(root, "isLightOn"), 0)
        self.assertEqual(len(nbt.get(root, "block_entities").values), 0)

    def test_unmodified_block_entities_retained(self):
        source = java_world(self.path / "java")
        doc = Document(open_world(source))
        doc.selection = Selection((1, 2, 3), (1, 2, 3))
        doc.fill(Block("glass"))
        doc.world.export(self.path / "out", doc.edits)
        _, root = nbt.loads(Region.read(self.path / "out/region/r.0.0.mca").get(0, 0))
        entities = nbt.get(root, "block_entities").values
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["x"].value, 2)

    def test_java_cross_chunk_and_region_edits(self):
        doc = Document(open_world(java_world(self.path / "java")))
        points = [(-1, 2, -1), (0, 2, 0), (16, 2, 0), (511, 2, 0), (512, 2, 0)]
        doc.apply("cross-boundary", ((p, Block("glass")) for p in points))
        doc.world.export(self.path / "out", doc.edits)
        reopened = open_world(self.path / "out")
        for point in points:
            with self.subTest(point=point):
                self.assertEqual(reopened.get_block(*point), Block("glass"))

    def test_java_new_negative_y_section(self):
        doc = Document(open_world(java_world(self.path / "java")))
        doc.apply("below zero", [((1, -35, 1), Block("deepslate"))])
        doc.world.export(self.path / "out", doc.edits)
        self.assertEqual(open_world(self.path / "out").get_block(1, -35, 1), Block("deepslate"))

    def test_older_java_paletted_layouts(self):
        for version in (1451, 2230, 2586):
            with self.subTest(version=version):
                doc = Document(open_world(java_world(self.path / str(version), version)))
                doc.apply("legacy palette", [((1, 5, 2), Block("glass"))])
                out = self.path / f"out{version}"
                doc.world.export(out, doc.edits)
                self.assertEqual(open_world(out).get_block(1, 5, 2), Block("glass"))

    def test_unsupported_version_and_missing_chunk(self):
        with self.assertRaises(nbt.FormatError):
            open_world(java_world(self.path / "future", 99999))
        doc = Document(open_world(java_world(self.path / "java")))
        with self.assertRaises(ValueError):
            doc.apply("uncreated", [((100000, 2, 100000), Block("stone"))])
        self.assertEqual(doc.world.bounds("the_nether"), (0,255))

    def test_bedrock_edit_export_reopen_source_unchanged(self):
        source = bedrock_world(self.path / "bedrock")
        original = hashes(source)
        doc = Document(open_world(source))
        self.assertEqual(doc.get(1, 2, 3), Block("stone"))
        doc.apply("bedrock", [((1, 2, 3), Block("gold_block")), ((-1, 5, -1), Block("glass"))])
        doc.undo()
        self.assertEqual(doc.get(1, 2, 3), Block("stone"))
        doc.redo()
        out = self.path / "out"
        doc.world.export(out, doc.edits)
        reopened = open_world(out)
        self.assertEqual(reopened.get_block(1, 2, 3), Block("gold_block"))
        self.assertEqual(reopened.get_block(-1, 5, -1), Block("glass"))
        self.assertEqual(reopened.values[b"unrelated-key"], b"keep this payload")
        self.assertEqual(reopened.values[b"~local_player"], b"opaque player data")
        self.assertEqual(reopened.values[b"\x00"*8+b"1"], b"")
        self.assertEqual(original, hashes(source))

    def test_bedrock_add_subchunk(self):
        doc = Document(open_world(bedrock_world(self.path / "bedrock")))
        doc.apply("new subchunk", [((1, -50, 1), Block("stone"))])
        doc.world.export(self.path / "out", doc.edits)
        self.assertEqual(open_world(self.path / "out").get_block(1, -50, 1), Block("stone"))

    def test_source_change_blocks_export(self):
        source = java_world(self.path / "java")
        world = open_world(source)
        (source / "extra.dat").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "source world changed"):
            world.export(self.path / "out", {})
        self.assertFalse((self.path / "out").exists())

    def test_export_destination_constraints(self):
        world = open_world(java_world(self.path / "java"))
        with self.assertRaises(FileExistsError):
            world.export(world.path, {})
        with self.assertRaises(ValueError):
            world.export(world.path / "inside", {})

    def test_failed_export_leaves_no_partial_world(self):
        world = open_world(java_world(self.path / "java"))
        original = hashes(world.path)
        with mock.patch.object(world, "_write_edits", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                world.export(self.path / "out", {})
        self.assertFalse((self.path / "out").exists())
        self.assertFalse(list(self.path.glob(".facetedit-export-*")))
        self.assertEqual(hashes(world.path), original)

    def test_source_symlink_refused(self):
        source = java_world(self.path / "java")
        try:
            (source / "link").symlink_to(source / "extra.dat")
        except OSError:
            self.skipTest("Symlinks unavailable to this OS user")
        with self.assertRaises(ValueError):
            open_world(source)

    def test_structure_roundtrip_and_transformed_paste(self):
        doc = Document(SampleWorld())
        doc.selection = Selection((-8, 30, -8), (-7, 31, -6))
        doc.fill(Block.parse("oak_log[axis=x]"))
        doc.copy()
        path = self.path / "build.nbt"
        export_structure(doc.clipboard, path)
        loaded = import_structure(path)
        self.assertEqual(loaded, doc.clipboard)
        doc.clipboard = loaded
        self.assertEqual(doc.paste((2, 30, 2), turns=1), 12)
        self.assertEqual(doc.get(2, 30, 2), Block.parse("oak_log[axis=z]"))

    def test_structure_with_entities_refused(self):
        root = nbt.compound(size=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.INT, [1,1,1])), palette=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])), blocks=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [])), entities=nbt.Tag(nbt.LIST, nbt.ListValue(nbt.COMPOUND, [{}])))
        file = self.path / "entity.nbt"
        file.write_bytes(nbt.dumps(root))
        with self.assertRaisesRegex(ValueError, "Entity-bearing"):
            import_structure(file)

    def test_sample_project_roundtrip(self):
        doc = Document(SampleWorld())
        doc.selection = Selection((1, 40, 1), (2, 42, 2))
        doc.fill(Block("gold_block"))
        path = self.path / "sample.facetedit"
        save_project(doc, path)
        loaded = load_project(path)
        self.assertEqual(loaded.edits, doc.edits)
        self.assertEqual(loaded.get(1, 40, 1), Block("gold_block"))

    def test_disk_project_rejects_changed_source(self):
        source = java_world(self.path / "java")
        doc = Document(open_world(source))
        doc.apply("edit", [((1,2,3), Block("glass"))])
        file = self.path / "project.facetedit"
        save_project(doc, file)
        self.assertEqual(load_project(file).edits, doc.edits)
        (source / "extra.dat").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            load_project(file)

    def test_invalid_project(self):
        file = self.path / "bad.facetedit"
        file.write_text('{"format":"facetedit-project","version":999}')
        with self.assertRaises(ValueError):
            load_project(file)

    def test_bedrock_mcstructure_roundtrip(self):
        doc = Document(open_world(bedrock_world(self.path / "bedrock")))
        doc.selection = Selection((0, 0, 0), (2, 1, 3))
        doc.copy()
        file = self.path / "build.mcstructure"
        export_structure(doc.clipboard, file)
        loaded = import_mcstructure(file)
        self.assertEqual(loaded, doc.clipboard)
        self.assertEqual(loaded.edition, "Bedrock")

    def test_bedrock_state_types_survive_project_and_clipboard(self):
        from facetedit.formats import bedrock_block, bedrock_entry
        entry = nbt.compound(name=nbt.Tag(nbt.STRING, "test:typed"), states=nbt.compound(a=nbt.Tag(nbt.BYTE, 1), b=nbt.Tag(nbt.INT, 1), c=nbt.Tag(nbt.STRING, "1")), version=nbt.Tag(nbt.INT, 17959425))
        block = bedrock_block(entry)
        doc = Document(open_world(bedrock_world(self.path / "bedrock")))
        doc.apply("typed", [((0, 0, 0), block)])
        project = self.path / "typed.facetedit"
        save_project(doc, project)
        reopened = load_project(project)
        self.assertEqual(reopened.get(0, 0, 0), block)
        self.assertEqual(bedrock_entry(reopened.get(0,0,0)).value["states"], entry.value["states"])
        doc.selection = Selection((0,0,0), (0,0,0))
        doc.copy()
        file = self.path / "typed.mcstructure"
        export_structure(doc.clipboard, file)
        self.assertEqual(import_mcstructure(file).blocks[(0,0,0)], block)

    def test_bedrock_direction_transform_preserves_typed_state(self):
        doc = Document(open_world(bedrock_world(self.path / "bedrock")))
        doc.selection = Selection((0,0,0), (0,0,0))
        doc.apply('stairs',[((0,0,0),Block('oak_stairs',(('weirdo_direction','0'),),(('weirdo_direction',nbt.INT),)))])
        doc.copy();doc.paste((1,0,0),turns=1)
        self.assertEqual(doc.get(1,0,0),Block('oak_stairs',(('weirdo_direction','2'),),(('weirdo_direction',nbt.INT),)))

    def test_bedrock_textual_noop_preserves_state_types(self):
        doc = Document(open_world(bedrock_world(self.path / "bedrock")))
        block = Block("test:typed", (("numeric_string", "1"),), (("numeric_string", nbt.STRING),))
        doc.apply("typed", [((0,0,0), block)])
        doc.selection = Selection((0,0,0), (0,0,0))
        self.assertEqual(doc.fill(Block.parse("test:typed[numeric_string=1]")), 0)
        self.assertEqual(doc.get(0,0,0), block)
        self.assertEqual(doc.fill(Block("glass"), replace=Block.parse("test:typed[numeric_string=1]")), 1)

    def test_cross_edition_clipboard_refused(self):
        from facetedit.model import Clipboard
        doc = Document(SampleWorld())
        doc.clipboard = Clipboard((1,1,1), {(0,0,0): Block("stone")}, "Bedrock")
        with self.assertRaisesRegex(ValueError, "Cross-edition"):
            doc.paste(origin=(0,30,0))

    def test_project_escaped_property_values_preserved(self):
        doc = Document(SampleWorld())
        block = Block("test:block", (("key", "value,with=[punctuation]"),))
        doc.apply("custom", [((0,30,0), block)])
        file = self.path / "escaped.facetedit"
        save_project(doc, file)
        self.assertEqual(load_project(file).get(0,30,0), block)

    def test_settings_validate_and_recover(self):
        file = self.path / "preferences.json"
        file.write_text('{"version":1,"recent":[1,"/tmp/world"],"radius":999,"grid":false}')
        settings = Settings(file)
        self.assertEqual(settings.data["recent"], ["/tmp/world"])
        self.assertEqual(settings.data["radius"], 12)
        self.assertFalse(settings.data["grid"])
        file.write_text("broken")
        settings = Settings(file)
        self.assertIsNotNone(settings.warning)
        settings.remember(self.path)
        self.assertEqual(Settings(file).data["recent"], [str(self.path)])

    def test_no_amulet_imports(self):
        import ast
        import facetedit
        imports = set()
        for file in Path(facetedit.__file__).parent.glob("*.py"):
            tree = ast.parse(file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imports.add((node.module or "").split(".")[0])
        import sys
        self.assertFalse(imports - sys.stdlib_module_names - {"facetedit"})

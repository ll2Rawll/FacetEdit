"""Containers must survive editing and every advertised structure format."""
from pathlib import Path
import tempfile
import unittest

from facetedit import nbt
from facetedit.blocks import AIR, Block
from facetedit.entities import relocate
from facetedit.model import Clipboard,Document,Selection
from facetedit.schematic import load_schematic,save_schematic
from facetedit.structures import export_structure,import_structure,import_mcstructure,save_project,load_project
from facetedit.world import SampleWorld,open_world
from tests.fixtures import java_world,bedrock_world
from tests.test_workflows import hashes


class EntityClipboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def document(self,edition='Java'):
        make = java_world if edition=='Java' else bedrock_world
        doc = Document(open_world(make(self.path/edition)))
        data = nbt.loads(doc.get_entity(1,2,3))[1]
        data.value['Items'] = nbt.Tag(nbt.LIST,nbt.ListValue(nbt.COMPOUND,[{
            'id':nbt.Tag(nbt.STRING,'minecraft:diamond'),
            'Count':nbt.Tag(nbt.BYTE,17),'Slot':nbt.Tag(nbt.BYTE,4)}]))
        data.value['CustomName'] = nbt.Tag(nbt.STRING,'Treasure 世界')
        doc.set_entity((1,2,3),data)
        doc.selection = Selection((1,2,3),(1,2,3))
        return doc

    def assertPayload(self,data,position):
        self.assertIsNotNone(data)
        tag = nbt.loads(data)[1]
        self.assertEqual(tuple(nbt.get(tag,axis) for axis in 'xyz'),position)
        self.assertEqual(nbt.get(tag,'CustomName'),'Treasure 世界')
        items = nbt.get(tag,'Items').values
        self.assertEqual(items[0]['Count'],nbt.Tag(nbt.BYTE,17))

    def test_copy_paste_export_reopen_both_editions(self):
        for edition in ('Java','Bedrock'):
            with self.subTest(edition=edition):
                doc = self.document(edition)
                before = hashes(doc.world.path)
                doc.copy()
                self.assertPayload(doc.clipboard.entities[(0,0,0)],(0,0,0))
                doc.paste((4,2,3))
                self.assertPayload(doc.get_entity(4,2,3),(4,2,3))
                doc.undo();self.assertIsNone(doc.get_entity(4,2,3))
                doc.redo()
                target = self.path/(edition+'-out')
                doc.world.export(target,doc.edits,entity_edits=doc.entity_edits)
                self.assertPayload(open_world(target).get_block_entity(4,2,3),(4,2,3))
                self.assertEqual(hashes(doc.world.path),before)

    def test_same_block_paste_clears_target_nbt_and_undo_restores(self):
        doc = self.document()
        original = doc.get_entity(1,2,3)
        doc.clipboard = Clipboard((1,1,1),{(0,0,0):Block('stone')})
        self.assertEqual(doc.paste((1,2,3)),1)
        self.assertIsNone(doc.get_entity(1,2,3))
        doc.undo();self.assertEqual(doc.get_entity(1,2,3),original)

    def test_cut_keeps_clipboard_and_undo_restores_container(self):
        doc = self.document()
        doc.cut()
        self.assertEqual(doc.get(1,2,3),AIR)
        self.assertIsNone(doc.get_entity(1,2,3))
        self.assertPayload(doc.clipboard.entities[(0,0,0)],(0,0,0))
        doc.undo();self.assertPayload(doc.get_entity(1,2,3),(1,2,3))

    def test_overlapping_clone_keeps_payload_and_one_undo_step(self):
        doc = self.document()
        depth = len(doc.undo_stack)
        doc.clone((1,0,0),3)
        for x in (2,3,4):self.assertPayload(doc.get_entity(x,2,3),(x,2,3))
        self.assertEqual(len(doc.undo_stack),depth+1)
        doc.undo();self.assertIsNone(doc.get_entity(4,2,3))

    def test_transforms_relocate_block_nbt_and_keep_inventory(self):
        doc = self.document();doc.copy()
        edits = dict(doc.edits);entities = dict(doc.entity_edits)
        for options in ({'turns':1},{'mirror':True}):
            doc.paste((4,2,3),**options)
            self.assertPayload(doc.get_entity(4,2,3),(4,2,3))
            doc.undo()
            self.assertEqual(doc.edits,edits);self.assertEqual(doc.entity_edits,entities)

    def test_unchanged_payload_with_changed_block_survives_delta_optimization(self):
        doc = Document(open_world(java_world(self.path/'Java')))
        original = doc.get_entity(1,2,3)
        local = relocate(original,(0,0,0))
        doc.clipboard = Clipboard((1,1,1),{(0,0,0):Block('chest')},entities={(0,0,0):local})
        doc.paste((1,2,3))
        self.assertEqual(doc.get_entity(1,2,3),original)
        project = self.path/'same.facet';save_project(doc,project)
        loaded = load_project(project)
        self.assertEqual(loaded.get_entity(1,2,3),original)
        target = self.path/'out'
        loaded.world.export(target,loaded.edits,entity_edits=loaded.entity_edits)
        self.assertEqual(open_world(target).get_block_entity(1,2,3),original)
        doc.undo();self.assertFalse(doc.edits);self.assertFalse(doc.entity_edits)
        doc.redo();self.assertEqual(doc.get_entity(1,2,3),original)

    def test_deleted_nbt_does_not_reappear_when_filling_original_block(self):
        doc = self.document()
        doc.fill(Block('glass'));doc.fill(Block('stone'))
        self.assertIsNone(doc.get_entity(1,2,3))
        self.assertTrue(doc.entity_edits)
        doc.undo();doc.undo();self.assertPayload(doc.get_entity(1,2,3),(1,2,3))

    def test_java_structure_inventory_roundtrip(self):
        doc = self.document();doc.copy()
        file = self.path/'chest.nbt';export_structure(doc.clipboard,file)
        loaded = import_structure(file)
        self.assertEqual(loaded,doc.clipboard)
        self.assertPayload(loaded.entities[(0,0,0)],(0,0,0))

    def test_mcstructure_inventory_roundtrip(self):
        doc = self.document('Bedrock');doc.copy()
        file = self.path/'chest.mcstructure';export_structure(doc.clipboard,file)
        loaded = import_mcstructure(file)
        self.assertEqual(loaded,doc.clipboard)
        self.assertPayload(loaded.entities[(0,0,0)],(0,0,0))

    def test_mcstructure_rejects_unsupported_tick_payload(self):
        doc = self.document('Bedrock');doc.copy()
        file = self.path/'tick.mcstructure';export_structure(doc.clipboard,file)
        root = nbt.loads(file.read_bytes(),little=True)[1]
        entry = root.value['structure'].value['palette'].value['default'].value['block_position_data'].value['0']
        entry.value['tick_queue_data'] = nbt.compound()
        file.write_bytes(nbt.dumps(root,little=True))
        with self.assertRaisesRegex(ValueError,'scheduled-tick'):
            import_mcstructure(file)

    def test_sponge_inventory_v2_and_v3(self):
        doc = self.document();doc.copy()
        for version in (2,3):
            with self.subTest(version=version):
                file = self.path/f'v{version}.schem'
                save_schematic(doc.clipboard,file,version)
                loaded = load_schematic(file)
                self.assertPayload(loaded.entities[(0,0,0)],(0,0,0))
                self.assertEqual(nbt.loads(loaded.entities[(0,0,0)])[1],nbt.loads(doc.clipboard.entities[(0,0,0)])[1])
                root = nbt.loads(file.read_bytes(),compressed=True)[1]
                block_root = root if version==2 else root.value['Schematic'].value['Blocks']
                entry = nbt.get(block_root,'BlockEntities').values[0]
                self.assertEqual(entry['Id'].value,'minecraft:chest')
                self.assertEqual(entry['Pos'],nbt.Tag(nbt.INT_ARRAY,[0,0,0]))
                self.assertEqual('Data' in entry,version==3)

    def test_sponge_duplicate_or_out_of_bounds_entities_refused(self):
        doc = self.document();doc.copy()
        file = self.path/'invalid.schem';save_schematic(doc.clipboard,file)
        root = nbt.loads(file.read_bytes(),compressed=True)[1]
        entries = root.value['Schematic'].value['Blocks'].value['BlockEntities'].value.values
        entries.append(dict(entries[0]))
        file.write_bytes(nbt.dumps(root,compressed=True))
        with self.assertRaisesRegex(ValueError,'duplicated'):load_schematic(file)
        entries.pop();entries[0]['Pos'] = nbt.Tag(nbt.INT_ARRAY,[2,0,0])
        file.write_bytes(nbt.dumps(root,compressed=True))
        with self.assertRaisesRegex(ValueError,'outside'):load_schematic(file)

    def test_bedrock_paired_chest_coordinates_relocate(self):
        data = nbt.compound(id=nbt.Tag(nbt.STRING,'Chest'),x=nbt.Tag(nbt.INT,10),y=nbt.Tag(nbt.INT,20),z=nbt.Tag(nbt.INT,-10),pairx=nbt.Tag(nbt.INT,11),pairz=nbt.Tag(nbt.INT,-10))
        result = nbt.loads(relocate(nbt.dumps(data),(0,0,0)))[1]
        self.assertEqual(nbt.get(result,'pairx'),1)
        self.assertEqual(nbt.get(result,'pairz'),0)

    def test_legacy_sample_generator_retained(self):
        doc = Document(SampleWorld(1))
        file = self.path/'old.facet';save_project(doc,file)
        loaded = load_project(file)
        self.assertEqual(loaded.world.generator,1)
        self.assertEqual(loaded.get(12,18,-10),doc.get(12,18,-10))
        self.assertEqual(SampleWorld().generator,2)

    def test_export_refuses_losing_schematic_offset(self):
        clip = Clipboard((1,1,1),{(0,0,0):Block('stone')},offset=(2,0,0))
        with self.assertRaisesRegex(ValueError,'offset'):
            export_structure(clip,self.path/'offset.nbt')

    def test_java_version_is_preserved_and_incompatible_paste_refused(self):
        old = Document(open_world(java_world(self.path/'old',version=2230)))
        old.selection = Selection((0,0,0),(0,0,0));old.copy()
        self.assertEqual(old.clipboard.data_version,2230)
        for extension,save,load in (('nbt',export_structure,import_structure),('schem',save_schematic,load_schematic)):
            file = self.path/('old.'+extension);save(old.clipboard,file)
            clip = load(file);self.assertEqual(clip.data_version,2230)
            doc = Document(SampleWorld());doc.clipboard = clip
            with self.assertRaisesRegex(ValueError,'Cross-version'):
                doc.paste((0,30,0))
            self.assertFalse(doc.edits)

    def test_bedrock_secondary_layers_are_not_silently_lost(self):
        from facetedit.formats import encode_bedrock
        doc = self.document('Bedrock')
        primary,secondary = [Block('stone')]*4096,[AIR]*4096
        secondary[(1<<8)|(3<<4)|2] = Block('water')
        doc.world.values[b'\x00'*8+b'/\x00'] = encode_bedrock(9,0,[primary,secondary],[])
        doc.copy();self.assertEqual(doc.clipboard.extra_blocks[(0,0,0)],(Block('water'),))
        doc.clone((1,0,0));self.assertEqual(doc.get_extra_blocks(2,2,3),(Block('water'),))
        doc.undo()
        doc.fill(Block('glass'))  # Replacing the block deliberately clears water.
        doc.copy()
        self.assertEqual(doc.clipboard.blocks[(0,0,0)],Block('glass'))

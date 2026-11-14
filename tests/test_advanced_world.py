from pathlib import Path
import tempfile
import unittest

from facetedit import nbt
from facetedit.converter import prepare_conversion,publish_conversion
from facetedit.model import Document,Selection
from facetedit.structures import export_structure,import_mcstructure
from facetedit.world import open_world
from tests.advanced_fixture import gallery
from tests.test_conversion import plain_java,modern_bedrock
from tests.test_workflows import hashes


class AdvancedWorldTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        self.source=plain_java(self.path/'java');self.positions=gallery(self.source);self.target=open_world(modern_bedrock(self.path/'bedrock'))

    def convert(self,source,target,name):
        plan=prepare_conversion(source,target);self.addCleanup(plan.close)
        self.assertTrue(plan.report.ok,plan.report.summary())
        return Document(open_world(publish_conversion(plan,self.path/name)))

    def test_native_world_roundtrip_keeps_books_timers_slots_and_section_context(self):
        source_hashes,template_hashes=hashes(self.source.world.path),hashes(self.target.path)
        native=self.convert(self.source,self.target,'converted')
        def entity(doc,label):return nbt.loads(doc.get_entity(*self.positions[label]))[1].value
        self.assertEqual(entity(native,'campfire')['ItemTime3'],nbt.Tag(nbt.INT,37))
        self.assertEqual(entity(native,'lectern')['book'].value['tag'].value['title'].value,'Builder notes')
        self.assertEqual(entity(native,'bookshelf')['LastInteractedSlot'],nbt.Tag(nbt.INT,6))
        self.assertEqual(entity(native,'piston')['State'],nbt.Tag(nbt.BYTE,2))
        brew=entity(native,'brewing');self.assertEqual(brew['CookTime'],nbt.Tag(nbt.SHORT,123))
        slots={item['Slot'].value:item for item in brew['Items'].value.values};self.assertEqual(slots[1]['Damage'].value,34)
        self.assertEqual(entity(native,'crafter')['disabled_slots'],nbt.Tag(nbt.SHORT,(1<<2)|(1<<5)|(1<<8)))
        restored=self.convert(native,self.source.world,'restored')
        for label,pos in self.positions.items():self.assertEqual(restored.get(*pos),self.source.get(*pos),label)
        self.assertEqual(entity(restored,'campfire')['CookingTimes'].value,[0,0,37,0])
        self.assertEqual(entity(restored,'lectern')['Page'].value,1)
        self.assertEqual(entity(restored,'bookshelf')['last_interacted_slot'].value,5)
        self.assertEqual(entity(restored,'gateway')['exit_portal'],nbt.Tag(nbt.INT_ARRAY,[-19,70,32]))
        self.assertIsNone(restored.get_entity(*self.positions['piston']))
        self.assertEqual(hashes(self.source.world.path),source_hashes);self.assertEqual(hashes(self.target.path),template_hashes)

    def test_structure_relocation_mirror_and_undo_preserve_new_payloads(self):
        native=self.convert(self.source,self.target,'converted')
        native.selection=Selection((0,15,0),(17,25,11));native.copy();clip=native.clipboard
        path=self.path/'gallery.mcstructure';export_structure(clip,path);loaded=import_mcstructure(path)
        self.assertEqual(loaded.blocks,clip.blocks);self.assertEqual(loaded.entities,clip.entities)
        original=native.get_entity(*self.positions['bookshelf'])
        native.clipboard=loaded.transformed(1,True);native.selection=Selection((32,20,0),(43,30,17));native.create_chunks()
        native.selection=Selection((32,20,0),(32,20,0));native.paste()
        native.undo();self.assertEqual(native.get_entity(*self.positions['bookshelf']),original)
        native.redo();self.assertTrue(native.entity_edits)

    def test_unsupported_native_book_photo_prevents_whole_world_publication(self):
        native=self.convert(self.source,self.target,'converted');position=self.positions['lectern']
        value=nbt.loads(native.get_entity(*position))[1]
        value.value['book'].value['tag'].value['pages'].value.values[0]['photoname']=nbt.Tag(nbt.STRING,'photo.png')
        native.set_entity(position,value);before=hashes(native.world.path)
        plan=prepare_conversion(native,self.source.world);self.addCleanup(plan.close)
        self.assertFalse(plan.report.ok);self.assertIn('photoname',plan.report.summary())
        with self.assertRaises(ValueError):publish_conversion(plan,self.path/'must-not-exist')
        self.assertFalse((self.path/'must-not-exist').exists());self.assertEqual(hashes(native.world.path),before)

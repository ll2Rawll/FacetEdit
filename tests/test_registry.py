import unittest

from facetedit.blocks import Block
from facetedit.registry import for_version, profile


class RegistryTests(unittest.TestCase):
    def test_primary_source_counts_and_known_defaults(self):
        java = profile('Java 1.21.4')
        bedrock = profile('Bedrock 1.21.50')
        self.assertEqual(len(java.blocks), 1095)
        self.assertEqual(len(bedrock.blocks), 1241)
        self.assertEqual(dict(java.initial('minecraft:oak_stairs').properties), {'facing':'north','half':'bottom','shape':'straight','waterlogged':'false'})
        self.assertIsNone(bedrock.blocks['minecraft:oak_stairs']['default'])

    def test_all_initial_states_validate_with_correct_types(self):
        for name in ('Java 1.21.4', 'Bedrock 1.21.50'):
            schema = profile(name)
            for block in schema.blocks:
                initial = schema.initial(block)
                self.assertEqual(schema.validate(initial), initial)
        self.assertEqual(dict(profile('Bedrock 1.21.50').initial('minecraft:oak_stairs').state_types), {'upside_down_bit':1,'weirdo_direction':3})

    def test_schema_mismatch_unknown_version_and_invalid_state_refused(self):
        java = profile('Java 1.21.4')
        for block in (Block('unknown_block'), Block.parse('oak_stairs[facing=up]'), Block.parse('stone[axis=y]')):
            with self.assertRaises(ValueError):
                java.validate(block)
        with self.assertRaises(ValueError):
            for_version('Java', 4188)
        with self.assertRaises(ValueError):
            for_version('Bedrock', game_version=(1,21,51))
        self.assertEqual(java.validate(Block('oak_stairs'), defaults=True), java.initial('minecraft:oak_stairs'))

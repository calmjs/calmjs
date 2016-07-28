# -*- coding: utf-8 -*-
import unittest
from pkg_resources import EntryPoint

from calmjs.module import ModuleRegistry


class ModuleTestCase(unittest.TestCase):
    """
    Test the JavaScript module registry.
    """

    def setUp(self):
        self.registry = ModuleRegistry(__name__)
        self.registry._init()

    def tearDown(self):
        pass

    def test_module_registry_empty(self):
        self.assertEqual(self.registry.module_map, {})

    def test_module_registry_standard(self):
        self.registry.register_entry_points([
            EntryPoint.parse(
                'calmjs.testing.module1 = calmjs.testing.module1'),
        ])
        self.assertEqual(sorted(self.registry.module_map.keys()), [
            'calmjs.testing.module1',
        ])

        module1 = self.registry.module_map['calmjs.testing.module1']
        key = 'calmjs/testing/module1/hello'
        self.assertEqual(sorted(module1.keys()), [key])
        self.assertTrue(module1[key].endswith(key + '.js'))

    def test_module_registry_extras(self):
        # This may be an awful abuse of entry_point extras, will need to
        # figure out how to do this properly.
        self.registry.register_entry_points([
            EntryPoint.parse(
                'calmjs.testing.module1 = calmjs.testing.module1 '
                '[calmjs.indexer.mapper_python]'
            ),
            # this should do nothing.
            EntryPoint.parse(
                'calmjs.testing.module2 = calmjs.testing.module2 '
                '[calmjs.bad.entry_point]'
            ),
        ])
        self.assertEqual(sorted(self.registry.module_map.keys()), [
            'calmjs.testing.module1',
        ])

        module1 = self.registry.module_map['calmjs.testing.module1']
        key = 'calmjs.testing.module1.hello'
        self.assertEqual(sorted(module1.keys()), [key])
        self.assertTrue(module1[key].endswith(
            'calmjs/testing/module1/hello.js'))

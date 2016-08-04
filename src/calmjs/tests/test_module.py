# -*- coding: utf-8 -*-
import unittest
from pkg_resources import EntryPoint
from pkg_resources import iter_entry_points

from calmjs.module import ModuleRegistry
from calmjs.module import PythonicModuleRegistry


@unittest.skipIf(
    list(iter_entry_points(__name__)),
    'basic module tests cannot run if %s is used as entry_point' % __name__)
class ModuleRegistryTestCase(unittest.TestCase):
    """
    Test the JavaScript module registry.
    """

    def setUp(self):
        self.registry = ModuleRegistry(__name__)

    def test_module_registry_empty(self):
        with self.assertRaises(StopIteration):
            next(self.registry.iter_records())

    def test_module_registry_standard(self):
        self.registry.register_entry_points([
            EntryPoint.parse(
                'calmjs.testing.module1 = calmjs.testing.module1'),
        ])
        self.assertEqual(sorted(
            key for key, value in self.registry.iter_records()
        ), [
            'calmjs.testing.module1',
        ])

        module1 = self.registry.get_record('calmjs.testing.module1')
        key = 'calmjs/testing/module1/hello'
        self.assertEqual(sorted(module1.keys()), [key])

    def test_module_registry_pythonic(self):
        registry = PythonicModuleRegistry(__name__)
        registry.register_entry_points([
            EntryPoint.parse(
                'calmjs.testing.module1 = calmjs.testing.module1'),
        ])
        self.assertEqual(sorted(
            key for key, value in registry.iter_records()
        ), [
            'calmjs.testing.module1',
        ])

        module1 = registry.get_record('calmjs.testing.module1')
        key = 'calmjs.testing.module1.hello'
        self.assertEqual(sorted(module1.keys()), [key])

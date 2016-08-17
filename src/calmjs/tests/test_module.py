# -*- coding: utf-8 -*-
import unittest
from pkg_resources import Distribution
from pkg_resources import EntryPoint

import calmjs.base
from calmjs.registry import Registry
from calmjs.registry import get
from calmjs.module import ModuleRegistry
from calmjs.module import PythonicModuleRegistry

from calmjs.testing import mocks
from calmjs.testing import utils


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


class IntegratedModuleRegistryTestCase(unittest.TestCase):
    """
    Test the JavaScript module registry, with a mocked working set and
    going through the root registry.
    """

    def test_module_registry_through_registry(self):
        """
        Show that the module registry instantiated through the global
        registry get function will result in the resulting module
        registry being populated properly with the module entries.
        """

        working_set = mocks.WorkingSet([
            'calmjs.module = calmjs.module:ModuleRegistry',
            'module1 = calmjs.testing.module1',
            'module2 = calmjs.testing.module2',
            'module3 = calmjs.testing.module3',
        ], dist=Distribution(project_name='calmjs.testing'))
        utils.stub_mod_working_set(self, [calmjs.base], working_set)

        # Not going to use the global registry
        local_root_registry = Registry(__name__)
        global_registry = get('calmjs.module')
        registry = local_root_registry.get_record('calmjs.module')
        self.assertIsNot(registry, global_registry)
        self.assertEqual(
            # the if v is to filter out the "global" dummy calmjs.module
            # entry, which normally isn't in production.
            sorted(k for k, v in registry.iter_records() if v), [
                'calmjs.testing.module1',
                'calmjs.testing.module2',
                'calmjs.testing.module3',
            ]
        )

        results = registry.get_records_for_package('calmjs.testing')
        self.assertEqual(sorted(results.keys()), [
           'calmjs/testing/module1/hello',
           'calmjs/testing/module2/helper',
           'calmjs/testing/module2/index',
           'calmjs/testing/module3/math',
        ])

        module1 = registry.get_record('calmjs.testing.module1')
        self.assertIn('calmjs/testing/module1/hello', module1)


class ExtraJsonKeysRegistryTestCase(unittest.TestCase):

    def test_integrated(self):
        """
        Since this module already immediately declares that, this can
        simply be a quick integration test.
        """

        reg = get('calmjs.extras_keys')
        results = set(reg.iter_records())
        self.assertIn('node_modules', results)

# -*- coding: utf-8 -*-
import unittest
from pkg_resources import EntryPoint

from calmjs import base
from calmjs.testing import mocks


class RegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def setUp(self):
        self.original_working_set = base.working_set

    def tearDown(self):
        base.working_set = self.original_working_set

    def test_base_module_registry(self):
        registry = base.BaseModuleRegistry('some_name')
        self.assertEqual(registry.registry_name, 'some_name')

    def test_base_module_registry_register_no_such_mod(self):
        registry = base.BaseModuleRegistry('some_name')
        registry.register_entry_points([
            EntryPoint.parse('calmjs.test = calmjs.no_such_mod')
        ])

    def test_base_module_registry_register_not_implemented(self):
        registry = base.BaseModuleRegistry('some_name')

        with self.assertRaises(NotImplementedError):
            registry.register_entry_points([
                EntryPoint.parse('calmjs = calmjs')])

    def test_base_module_registry_initialize_not_imp(self):
        with self.assertRaises(NotImplementedError):
            base.BaseModuleRegistry.initialize('some_name')

    def test_base_module_registry_initialize_subclassed(self):
        class DummyRegistry(base.BaseModuleRegistry):
            entry_point_name = 'clamjs.dummy_fake_name'

            def __init__(self, name, arg):
                self.arg = arg
                super(DummyRegistry, self).__init__(name)

        registry = DummyRegistry.initialize('some_name', 'some_arg')
        self.assertTrue(isinstance(registry, DummyRegistry))
        self.assertEqual(registry.registry_name, 'some_name')
        self.assertEqual(registry.arg, 'some_arg')

    def test_base_module_registry_missing_pkg_resources(self):
        # emulate initial import failure
        base.working_set = None

        class DummyRegistry(base.BaseModuleRegistry):
            entry_point_name = 'clamjs.dummy_fake_name'

            def __init__(self, name, arg):
                self.arg = arg
                super(DummyRegistry, self).__init__(name)

        registry = DummyRegistry.initialize('some_name', 'some_arg')
        self.assertTrue(isinstance(registry, DummyRegistry))
        self.assertEqual(registry.registry_name, 'some_name')
        self.assertEqual(registry.arg, 'some_arg')

    def test_base_module_registry_dummy_working_set(self):

        class DummyRegistry(base.BaseModuleRegistry):
            entry_point_name = 'clamjs.dummy_fake_name'

            def __init__(self, name, arg):
                self.arg = arg
                self.entry_points = []
                self.modules = []
                super(DummyRegistry, self).__init__(name)

            def _register_entry_point_module(self, entry_point, module):
                self.entry_points.append(entry_point)
                self.modules.append(module)

        working_set = mocks.WorkingSet([
            'module1 = calmjs.testing.module1',
            'module2 = calmjs.testing.module2',
            'module3 = calmjs.testing.module3',
        ])

        registry = DummyRegistry.initialize(
            'some_name', 'some_arg', _working_set=working_set)
        self.assertTrue(isinstance(registry, DummyRegistry))
        self.assertEqual(registry.registry_name, 'some_name')
        self.assertEqual(registry.arg, 'some_arg')

        self.assertEqual(len(registry.entry_points), 3)
        self.assertEqual(len(registry.modules), 3)

        self.assertEqual(
            registry.modules[0].__name__, 'calmjs.testing.module1')

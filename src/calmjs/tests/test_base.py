# -*- coding: utf-8 -*-
import unittest
from pkg_resources import EntryPoint

from calmjs import base


class RegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

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

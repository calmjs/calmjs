# -*- coding: utf-8 -*-
import unittest
from pkg_resources import EntryPoint

from calmjs import base
from calmjs.testing import mocks
from calmjs.testing import utils


class DummyRegistry(base.BaseModuleRegistry):
    entry_point_name = 'clamjs.dummy_fake_name'

    def _init(self, arg):
        self.arg = arg


class RegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def setUp(self):
        self.original_working_set = base.working_set
        utils.setup_testing_module_registry(self)

    def tearDown(self):
        base.working_set = self.original_working_set

    def test_module_registry_registration(self):
        registry = base.BaseModuleRegistry('some_name')
        base._ModuleRegistry.register('some_name', registry)
        self.assertEqual(base._ModuleRegistry.get('some_name'), registry)

        with self.assertRaises(KeyError):
            # no duplicates.
            base._ModuleRegistry.register('some_name', registry)

        with self.assertRaises(TypeError):
            base._ModuleRegistry.register('some_other_name', None)

        with self.assertRaises(LookupError):
            # no duplicates.
            base._ModuleRegistry.get('this_not_exist')

    def test_base_module_registry(self):
        registry = base.BaseModuleRegistry('some_name')
        self.assertEqual(registry.registry_name, 'some_name')

    def test_base_module_registry_register_no_such_mod(self):
        registry = base.BaseModuleRegistry('some_name')
        # `__builtin__.NoSuchThing` is not a valid item, thus it only
        # warns rather than invoking _register_entry_point_module which
        # triggers NotImplementedError
        registry.register_entry_points([
            EntryPoint.parse('calmjs.test = __builtin__.NoSuchThing')
        ])
        # no exceptions raised, but we got nothing to validate against.

    def test_base_module_registry_register_not_implemented(self):
        registry = base.BaseModuleRegistry('some_name')
        with self.assertRaises(NotImplementedError):
            # valid name, triggers the exception as outlined above.
            registry.register_entry_points([
                EntryPoint.parse('calmjs = calmjs')])

    def test_base_module_registry_initialize_not_imp(self):
        with self.assertRaises(NotImplementedError):
            base.BaseModuleRegistry.initialize('not_implemented')

    def test_base_module_registry_initialize_subclassed(self):
        registry = DummyRegistry.initialize('some_name', 'some_arg')
        self.assertTrue(isinstance(registry, DummyRegistry))
        self.assertEqual(registry.registry_name, 'some_name')
        self.assertEqual(registry.arg, 'some_arg')

    def test_base_module_registry_missing_pkg_resources(self):
        # emulate initial import failure
        base.working_set = None
        registry = DummyRegistry.initialize('some_name', 'some_arg')
        self.assertTrue(isinstance(registry, DummyRegistry))
        self.assertEqual(registry.registry_name, 'some_name')
        self.assertEqual(registry.arg, 'some_arg')

    def test_base_module_registry_dummy_working_set(self):

        class DummyRegistryAlt(base.BaseModuleRegistry):
            entry_point_name = 'clamjs.dummy_fake_name'

            def _init(self, arg):
                self.arg = arg
                self.entry_points = []
                self.modules = []

            def _register_entry_point_module(self, entry_point, module):
                self.entry_points.append(entry_point)
                self.modules.append(module)

        working_set = mocks.WorkingSet([
            'module1 = calmjs.testing.module1',
            'module2 = calmjs.testing.module2',
            'module3 = calmjs.testing.module3',
        ])

        registry = DummyRegistryAlt.initialize(
            'some_name', 'some_arg', _working_set=working_set)
        self.assertTrue(isinstance(registry, DummyRegistryAlt))
        self.assertEqual(registry.registry_name, 'some_name')
        self.assertEqual(registry.arg, 'some_arg')

        self.assertEqual(len(registry.entry_points), 3)
        self.assertEqual(len(registry.modules), 3)

        self.assertEqual(
            registry.modules[0].__name__, 'calmjs.testing.module1')

    def test_base_module_registry_registry_singleton(self):
        """
        Since using the same initialization pattern results in the
        singleton registry of the same name, this should be tested.
        """

        class DummyRegistryAlt(base.BaseModuleRegistry):
            entry_point_name = 'clamjs.dummy_fake_alt'

            def _init(self, arg):
                self.arg = arg

        registry1 = DummyRegistryAlt.initialize('some_name', 'some_arg')
        registry2 = DummyRegistryAlt.initialize('some_name', 'different_arg')
        self.assertTrue(isinstance(registry1, DummyRegistryAlt))
        # they should be the same object, even though registry2 got a
        # completely different initialization argument.
        self.assertEqual(registry1, registry2)
        # Note that the _init method will NOT be called again.
        self.assertEqual(registry2.arg, 'some_arg')

        # initializing a same registry using a different type but to the
        # same name should trigger a value error
        with self.assertRaises(ValueError):
            DummyRegistry.initialize('some_name')

        # Ditto for subclasses
        class DummyRegistryAltExt(base.BaseModuleRegistry):
            entry_point_name = 'clamjs.dummy_fake_alt_ext'

        with self.assertRaises(ValueError):
            DummyRegistryAltExt.initialize('some_name')

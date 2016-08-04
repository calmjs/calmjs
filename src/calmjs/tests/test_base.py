# -*- coding: utf-8 -*-
import unittest

from calmjs import base
from calmjs.testing import mocks


class DummyModuleRegistry(base.BaseModuleRegistry):

    def _register_entry_point_module(self, entry_point, module):
        # adding the module straight into the record
        self.records[entry_point.name] = module


class BaseRegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def test_empty(self):
        working_set = mocks.WorkingSet([])
        registry = base.BaseRegistry(__name__, _working_set=working_set)
        self.assertEqual(registry.raw_entry_points, [])

    def test_entry_points(self):
        working_set = mocks.WorkingSet([
            'module1 = calmjs.testing.module1',
            'module2 = calmjs.testing.module2',
            'module3 = calmjs.testing.module3',
        ])

        registry = base.BaseRegistry(__name__, _working_set=working_set)
        self.assertEqual(len(registry.raw_entry_points), 3)

    def test_not_implemented(self):
        registry = base.BaseRegistry(__name__)

        with self.assertRaises(NotImplementedError):
            registry.get_record('something')

        with self.assertRaises(NotImplementedError):
            registry.iter_records()


class BaseModuleRegistryTestCase(unittest.TestCase):
    """
    Test the base registry.
    """

    def setUp(self):
        self.original_working_set = base.working_set

    def tearDown(self):
        base.working_set = self.original_working_set

    def test_empty(self):
        working_set = mocks.WorkingSet([])
        registry = base.BaseModuleRegistry(__name__, _working_set=working_set)
        self.assertEqual(list(registry.iter_records()), [])

    def test_bad_record(self):
        working_set = mocks.WorkingSet([
            'calmjs.testing.not_a_module = calmjs.testing.not_a_module',
        ])
        registry = base.BaseModuleRegistry(__name__, _working_set=working_set)
        self.assertEqual(len(registry.raw_entry_points), 1)
        self.assertIsNone(registry.get_record('module'))
        self.assertEqual(list(registry.iter_records()), [])

    def test_not_implemented(self):
        working_set = mocks.WorkingSet([
            'calmjs.testing.module1 = calmjs.testing.module1',
        ])
        with self.assertRaises(NotImplementedError):
            base.BaseModuleRegistry(__name__, _working_set=working_set)

    def test_dummy_implemented(self):
        working_set = mocks.WorkingSet([
            'calmjs.testing.module1 = calmjs.testing.module1',
        ])
        registry = DummyModuleRegistry(__name__, _working_set=working_set)
        record = registry.get_record('calmjs.testing.module1')
        self.assertEqual(record.__name__, 'calmjs.testing.module1')
        self.assertEqual(list(registry.iter_records()), [
            ('calmjs.testing.module1', record)])

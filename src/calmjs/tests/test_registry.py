# -*- coding: utf-8 -*-
import unittest

from calmjs.base import BaseRegistry

import calmjs.registry

from calmjs.testing import mocks


class RegistryIntegrationTestCase(unittest.TestCase):
    """
    Test that the default entry points declared for this module against
    the ``calmjs.registry`` group resulted in the actual registry system
    being bootstrapped into existence
    """

    def test_successful_bootstrap_got_none(self):
        self.assertIsNone(calmjs.registry.get('no_such_registry'))

    def test_successful_bootstrap(self):
        module_registry = calmjs.registry.get('calmjs.module')
        # TODO check that actual type should be more specific
        self.assertTrue(isinstance(module_registry, BaseRegistry))
        # instance is cached.
        self.assertIs(module_registry, calmjs.registry.get('calmjs.module'))
        self.assertIs(module_registry, calmjs.registry._inst.get_record(
            'calmjs.module'))

    def test_registry_graceful_fail(self):
        working_set = mocks.WorkingSet([
            'failure = calmjs.testing.no_such_module:NoClass',
        ])
        registry = calmjs.registry.Registry(
            'calmjs.registry', _working_set=working_set)
        # This should not be registered or available
        self.assertIsNone(registry.get_record('calmjs.module'))
        self.assertIsNone(registry.get_record('failure'))

    def test_registry_graceful_fail_bad_constructor(self):
        working_set = mocks.WorkingSet([
            'failure = calmjs.testing.module3.module:NotRegistry',
        ])
        registry = calmjs.registry.Registry(
            'calmjs.registry', _working_set=working_set)
        # This should not be registered or available
        self.assertIsNone(registry.get_record('calmjs.module'))
        self.assertIsNone(registry.get_record('failure'))

    def test_registry_fresh_from_entrypoint(self):
        working_set = mocks.WorkingSet([
            'custom = calmjs.testing.module3.module:CustomModuleRegistry',
        ])
        registry = calmjs.registry.Registry(
            'calmjs.registry', _working_set=working_set)
        self.assertEqual(len(registry.records), 0)

        registry.get_record('custom')
        self.assertEqual(len(registry.records), 1)

        from calmjs.testing.module3.module import CustomModuleRegistry
        self.assertTrue(isinstance(
            registry.get_record('custom'), CustomModuleRegistry))

# -*- coding: utf-8 -*-
import unittest

import pkg_resources

import calmjs.registry
from calmjs.base import BaseRegistry
from calmjs.utils import pretty_logging

from calmjs.testing import mocks
from calmjs.testing.utils import make_dummy_dist


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
        working_set = mocks.WorkingSet({'calmjs.registry': [
            'failure = calmjs.testing.no_such_module:NoClass',
        ]})
        registry = calmjs.registry.Registry(
            'calmjs.registry', _working_set=working_set)

        with pretty_logging(stream=mocks.StringIO()) as stream:
            self.assertIsNone(registry.get_record('calmjs.module'))
        self.assertIn("'calmjs.module' does not resolve", stream.getvalue())

        with pretty_logging(stream=mocks.StringIO()) as stream:
            self.assertIsNone(registry.get_record('failure'))
        self.assertIn("ImportError 'failure", stream.getvalue())

    def test_registry_graceful_fail_bad_constructor(self):
        working_set = mocks.WorkingSet({'calmjs.registry': [
            'failure = calmjs.testing.module3.module:NotRegistry',
        ]})
        registry = calmjs.registry.Registry(
            'calmjs.registry', _working_set=working_set)
        # This should not be registered or available
        self.assertIsNone(registry.get_record('calmjs.module'))

        with pretty_logging(stream=mocks.StringIO()) as stream:
            self.assertIsNone(registry.get_record('failure'))
        # exact error message differs between Python versions.
        self.assertIn('TypeError: __init__() ', stream.getvalue())

    def test_registry_fresh_from_entrypoint(self):
        working_set = mocks.WorkingSet({'calmjs.registry': [
            'custom = calmjs.testing.module3.module:CustomModuleRegistry',
        ]})
        registry = calmjs.registry.Registry(
            'calmjs.registry', _working_set=working_set)
        self.assertEqual(len(registry.records), 0)

        registry.get_record('custom')
        self.assertEqual(len(registry.records), 1)

        from calmjs.testing.module3.module import CustomModuleRegistry
        self.assertTrue(isinstance(
            registry.get_record('custom'), CustomModuleRegistry))

    def test_registry_reserved(self):
        make_dummy_dist(self, ((
            'entry_points.txt',
            '[calmjs.reserved]\n'
            'calmjs.r1 = calmjs\n'
            'calmjs.r3 = an.external\n'
            '\n'
            '[calmjs.registry]\n'
            'calmjs.r1 = calmjs.module:ModuleRegistry\n'
            'calmjs.r2 = calmjs.module:ModuleRegistry\n'
            'calmjs.r3 = calmjs.module:ModuleRegistry\n'
        ),), 'calmjs', '1.0')

        make_dummy_dist(self, ((
            'requires.txt',
            'calmjs',
            ), (
            'entry_points.txt',
            '[calmjs.reserved]\n'
            'calmjs.r1 = an.external\n'
            'calmjs.r2 = calmjs\n'
            'calmjs.r3 = calmjs\n'
            '\n'
            '[calmjs.registry]\n'
            'calmjs.r1 = calmjs.testing.module3.module:CustomModuleRegistry\n'
            'calmjs.r2 = calmjs.testing.module3.module:CustomModuleRegistry\n'
            'calmjs.r3 = calmjs.testing.module3.module:CustomModuleRegistry\n'
        ),), 'an.external', '2.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        with pretty_logging(stream=mocks.StringIO()) as stream:
            registry = calmjs.registry.Registry(
                'calmjs.registry', _working_set=working_set)

        from calmjs.testing.module3.module import CustomModuleRegistry
        from calmjs.module import ModuleRegistry

        r1 = registry.get('calmjs.r1')
        r2 = registry.get('calmjs.r2')
        r3 = registry.get('calmjs.r3')

        # since this one is reserved to calmjs, not registered
        self.assertFalse(isinstance(r1, CustomModuleRegistry))
        self.assertTrue(isinstance(r1, ModuleRegistry))
        # whatever this is.
        self.assertTrue(isinstance(r2, ModuleRegistry))
        # this one is reserved to an.external
        self.assertTrue(isinstance(r3, CustomModuleRegistry))

        log = stream.getvalue()
        self.assertIn(
            "registry 'calmjs.r1' for 'calmjs.registry' is reserved for "
            "package 'calmjs'", log
        )
        self.assertIn(
            "registry 'calmjs.r3' for 'calmjs.registry' is reserved for "
            "package 'an.external'", log
        )
        self.assertIn(
            "registry 'calmjs.r2' for 'calmjs.registry' is already registered",
            log
        )

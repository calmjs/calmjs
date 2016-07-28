# -*- coding: utf-8 -*-
import unittest

from calmjs.base import BaseModuleRegistry
from calmjs.registry import get_module_registry

from calmjs.testing import utils


class DummyModuleRegistry(BaseModuleRegistry):
    entry_point_name = 'dummy'


class RegistryTestCase(unittest.TestCase):

    def setUp(self):
        utils.setup_testing_module_registry(self)

    def tearDown(self):
        pass

    def test_get_module_registry(self):
        foo = DummyModuleRegistry.initialize('foo')
        bar = DummyModuleRegistry.initialize('bar')

        self.assertEqual(foo, get_module_registry('foo'))
        self.assertEqual(bar, get_module_registry('bar'))

        with self.assertRaises(LookupError):
            get_module_registry('no_such_registry')

# -*- coding: utf-8 -*-
import unittest

from types import ModuleType
from os.path import abspath
from os.path import dirname
from os.path import join
from os.path import pardir
from os.path import relpath
import sys

import calmjs
from calmjs import loader

calmjs_base_dir = abspath(join(dirname(calmjs.__file__), pardir))


class GlobLoaderTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_modpath_single_empty(self):
        module = ModuleType('nothing')
        self.assertEqual(loader.modpath_single(module), [])

    def test_get_modpath_single_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(loader.modpath_single(module), ['/path/to/there'])

    def test_get_modpath_all_empty(self):
        module = ModuleType('nothing')
        self.assertEqual(loader.modpath_all(module), [])

    def test_get_modpath_all_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(
            loader.modpath_all(module),
            ['/path/to/here', '/path/to/there'],
        )

    def test_module1_loader_default(self):
        from calmjs.testing import module1
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in loader.default(module1).items()
        }
        self.assertEqual(results, {
            'calmjs/testing/module1/hello': 'calmjs/testing/module1/hello.js',
        })

    def test_module1_loader_default_py(self):
        from calmjs.testing import module1
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in loader.default_py(module1).items()
        }
        self.assertEqual(results, {
            'calmjs.testing.module1.hello': 'calmjs/testing/module1/hello.js',
        })

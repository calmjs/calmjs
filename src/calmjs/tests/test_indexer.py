# -*- coding: utf-8 -*-
import unittest
from shutil import rmtree
from tempfile import mkdtemp

from os import makedirs
from os.path import abspath
from os.path import dirname
from os.path import join
from os.path import pardir
from os.path import relpath

from types import ModuleType

import calmjs
from calmjs import indexer

calmjs_base_dir = abspath(join(dirname(calmjs.__file__), pardir))


class IndexerTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = None

    def tearDown(self):
        if self.tmpdir:
            rmtree(self.tmpdir)

    def mkdtemp(self):
        self.tmpdir = mkdtemp()
        return self.tmpdir

    def test_register(self):
        def bar_something():
            pass

        registry = {'foo': {}, 'bar': {}}
        with self.assertRaises(TypeError):
            indexer.register('foo', registry=registry)(bar_something)

        indexer.register('bar', registry=registry)(bar_something)
        self.assertEqual(registry['bar']['something'], bar_something)

    def test_get_modpath_last_empty(self):
        module = ModuleType('nothing')
        self.assertEqual(indexer.modpath_last(module), [])

    def test_get_modpath_last_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(indexer.modpath_last(module), ['/path/to/there'])

    def test_get_modpath_all_empty(self):
        module = ModuleType('nothing')
        self.assertEqual(indexer.modpath_all(module), [])

    def test_get_modpath_all_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(
            indexer.modpath_all(module),
            ['/path/to/here', '/path/to/there'],
        )

    def test_module1_loader_es6(self):
        from calmjs.testing import module1
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in indexer.mapper_es6(module1).items()
        }
        self.assertEqual(results, {
            'calmjs/testing/module1/hello': 'calmjs/testing/module1/hello.js',
        })

    def test_module1_loader_python(self):
        from calmjs.testing import module1
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in indexer.mapper_python(module1).items()
        }
        self.assertEqual(results, {
            'calmjs.testing.module1.hello': 'calmjs/testing/module1/hello.js',
        })

    def test_module2_recursive_es6(self):
        from calmjs.testing import module2
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in indexer.mapper(module2, globber='recursive').items()
        }
        self.assertEqual(results, {
            'calmjs/testing/module2/index':
                'calmjs/testing/module2/index.js',
            'calmjs/testing/module2/helper':
                'calmjs/testing/module2/helper.js',
            'calmjs/testing/module2/mod/helper':
                'calmjs/testing/module2/mod/helper.js',
        })

    def test_module3_multi_root(self):
        """
        For multiple roots.  This is typically caused by specifying a
        module that is typically used as a namespace for other Python
        modules.  Normally this can interfere with imports but as long
        as a module is produced and the multiple path modpath method
        is used, the mapper will fulfil the order.
        """

        from calmjs.testing import module3

        # We will cheat a bit to obtain what we need to do the test.
        # First create a tmpdir where the "alternative" module path will
        # be provided with a dummy JavaScript module file
        tmpdir = self.mkdtemp()
        target = join(
            self.tmpdir, 'calmjs.testing.module3', 'src',
            'calmjs', 'testing', 'module3')
        makedirs(target)
        index_js = join(target, 'index.js')

        with open(index_js, 'w') as fd:
            fd.write('"use strict";\n')
            fd.write('var math = require("calmjs/testing/module3/math");\n')
            fd.write('exports.main = function() {\n')
            fd.write('    console.log(math.add(1 + 1));\n')
            fd.write('};\n')

        # Then we create a dummy Python module that merges the paths
        # provided by the real module3 with the fake one we have.

        fake_modpath = [target] + module3.__path__
        module = ModuleType('calmjs.testing.module3')
        module.__path__ = fake_modpath

        # see how this works.

        results = indexer.mapper(module, modpath='all', globber='recursive')
        self.assertEqual(results, {
            'calmjs/testing/module3/index': index_js,
            'calmjs/testing/module3/math': join(
                calmjs_base_dir, 'calmjs', 'testing', 'module3', 'math.js'),
        })

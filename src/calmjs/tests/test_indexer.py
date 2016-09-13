# -*- coding: utf-8 -*-
import unittest

from os.path import abspath
from os.path import join
from os.path import pardir
from os.path import relpath
from os.path import sep

from types import ModuleType

from calmjs import indexer
from calmjs.utils import pretty_logging

from calmjs.testing.utils import make_multipath_module3
from calmjs.testing.mocks import StringIO


def to_os_sep_path(p):
    # turn the given / separated path into an os specific path
    return sep.join(p.split('/'))


class IndexerTestCase(unittest.TestCase):

    def test_register(self):
        def bar_something():
            "dummy method"

        registry = {'foo': {}, 'bar': {}}
        with self.assertRaises(TypeError):
            indexer.register('foo', registry=registry)(bar_something)

        indexer.register('bar', registry=registry)(bar_something)
        self.assertEqual(registry['bar']['something'], bar_something)

    def test_get_modpath_last_empty(self):
        module = ModuleType('nothing')
        with pretty_logging(stream=StringIO()) as fd:
            self.assertEqual(indexer.modpath_last(module), [])
        self.assertIn(
            "module 'nothing' does not appear to be a namespace module",
            fd.getvalue())

    def test_get_modpath_last_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(indexer.modpath_last(module), ['/path/to/there'])

    def test_get_modpath_all_empty(self):
        module = ModuleType('nothing')
        with pretty_logging(stream=StringIO()) as fd:
            self.assertEqual(indexer.modpath_all(module), [])
        self.assertIn(
            "module 'nothing' does not appear to be a namespace module",
            fd.getvalue())

    def test_get_modpath_all_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(
            indexer.modpath_all(module),
            ['/path/to/here', '/path/to/there'],
        )

    def test_get_modpath_pkg_resources_valid(self):
        from calmjs.testing import module3
        result = indexer.modpath_pkg_resources(module3)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].endswith(
            to_os_sep_path('calmjs/testing/module3')))

    def test_get_modpath_pkg_resources_invalid(self):
        with pretty_logging(stream=StringIO()) as fd:
            self.assertEqual([], indexer.modpath_pkg_resources(None))
            self.assertIn(
                "None does not appear to be a valid module", fd.getvalue())
        with pretty_logging(stream=StringIO()) as fd:
            module = ModuleType('nothing')
            self.assertEqual([], indexer.modpath_pkg_resources(module))
            # module repr differs between python versions.
            self.assertIn("module 'nothing'", fd.getvalue())
            self.assertIn("could not be located", fd.getvalue())

    def test_module1_loader_es6(self):
        from calmjs.testing import module1
        calmjs_base_dir = abspath(join(
            indexer.modpath_pkg_resources(indexer)[0], pardir))
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in indexer.mapper_es6(module1).items()
        }
        self.assertEqual(results, {
            'calmjs/testing/module1/hello':
                to_os_sep_path('calmjs/testing/module1/hello.js'),
        })

    def test_module1_loader_python(self):
        from calmjs.testing import module1
        calmjs_base_dir = abspath(join(
            indexer.modpath_pkg_resources(indexer)[0], pardir))
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in indexer.mapper_python(module1).items()
        }
        self.assertEqual(results, {
            'calmjs.testing.module1.hello':
                to_os_sep_path('calmjs/testing/module1/hello.js'),
        })

    def test_module2_recursive_es6(self):
        from calmjs.testing import module2
        calmjs_base_dir = abspath(join(
            indexer.modpath_pkg_resources(indexer)[0], pardir))
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in indexer.mapper(module2, globber='recursive').items()
        }
        self.assertEqual(results, {
            'calmjs/testing/module2/index':
                to_os_sep_path('calmjs/testing/module2/index.js'),
            'calmjs/testing/module2/helper':
                to_os_sep_path('calmjs/testing/module2/helper.js'),
            'calmjs/testing/module2/mod/helper':
                to_os_sep_path('calmjs/testing/module2/mod/helper.js'),
        })

    def test_module3_multi_path(self):
        """
        For modules that have multiple paths.  This is typically caused
        by specifying a module that is typically used as a namespace for
        other Python modules.  Normally this can interfere with imports
        but as long as a module is produced and the multiple path
        modpath method is used, the mapper will fulfil the order.
        """

        # See setup method for how it's built.
        calmjs_base_dir = abspath(join(
            indexer.modpath_pkg_resources(indexer)[0], pardir))
        module, index_js = make_multipath_module3(self)

        def join_mod3(*a):
            return join(calmjs_base_dir, 'calmjs', 'testing', 'module3', *a)

        results = indexer.mapper(module, modpath='all', globber='recursive')
        self.assertEqual(results, {
            'calmjs/testing/module3/index': index_js,
            'calmjs/testing/module3/math': join_mod3('math.js'),
            'calmjs/testing/module3/mod/index': join_mod3('mod', 'index.js'),
        })

    def test_module2_callables(self):
        from calmjs.testing import module2
        calmjs_base_dir = abspath(join(
            indexer.modpath_pkg_resources(indexer)[0], pardir))
        results = {
            k: relpath(v, calmjs_base_dir)
            for k, v in indexer.mapper(
                module2,
                globber=indexer.globber_recursive,
                modname=indexer.modname_python,
                modpath=indexer.modpath_pkg_resources,
            ).items()
        }
        self.assertEqual(results, {
            'calmjs.testing.module2.index':
                to_os_sep_path('calmjs/testing/module2/index.js'),
            'calmjs.testing.module2.helper':
                to_os_sep_path('calmjs/testing/module2/helper.js'),
            'calmjs.testing.module2.mod.helper':
                to_os_sep_path('calmjs/testing/module2/mod/helper.js'),
        })

# -*- coding: utf-8 -*-
import unittest
import os
import sys
import warnings

from os.path import abspath
from os.path import exists
from os.path import join
from os.path import normcase
from os.path import pardir
from os.path import relpath
from os.path import sep

from types import ModuleType
import pkg_resources

from calmjs import indexer
from calmjs.utils import pretty_logging

from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import make_multipath_module3
from calmjs.testing.utils import stub_item_attr_value
from calmjs.testing.utils import mkdtemp
from calmjs.testing.mocks import StringIO


def to_os_sep_path(p):
    # turn the given / separated path into an os specific path
    return sep.join(p.split('/'))


class PkgResourcesIndexTestCase(unittest.TestCase):
    """
    This series of tests muck with python module internals.
    """

    def setUp(self):
        # `dummyns.submod` emulates a package that also provide the
        # `dummyns` namespace package that got installed after the
        # other package `dummyns`.
        ds_egg_root = join(mkdtemp(self), 'dummyns.submod')
        dummyns_path = join(ds_egg_root, 'dummyns')
        dummyns = ModuleType('dummyns')
        dummyns.__file__ = join(dummyns_path, '__init__.py')
        dummyns.__path__ = [dummyns_path]
        sys.modules['dummyns'] = dummyns

        dummyns_submod_path = join(ds_egg_root, 'dummyns', 'submod')
        dummyns_submod = ModuleType('dummyns.submod')
        dummyns_submod.__file__ = join(dummyns_submod_path, '__init__.py')
        dummyns_submod.__path__ = [dummyns_submod_path]
        sys.modules['dummyns.submod'] = dummyns_submod

        os.makedirs(dummyns_submod_path)

        with open(join(dummyns_path, '__init__.py'), 'w') as fd:
            fd.write('')

        with open(join(dummyns_submod_path, '__init__.py'), 'w') as fd:
            fd.write('')

        self.nested_res = join(dummyns_submod_path, 'data.txt')
        self.nested_data = 'data'
        with open(self.nested_res, 'w') as fd:
            fd.write(self.nested_data)

        # create the package proper
        self.dummyns_submod_dist = make_dummy_dist(self, ((
            'namespace_packages.txt',
            'dummyns\n'
            'dummyns.submod\n',
        ), (
            'entry_points.txt',
            '[dummyns.submod]\n'
            'dummyns.submod = dummyns.submod:attr\n',
        ),), 'dummyns.submod', '1.0', working_dir=ds_egg_root)

        self.ds_egg_root = ds_egg_root
        self.dummyns_path = dummyns_path

        self.mod_dummyns = dummyns
        self.mod_dummyns_submod = dummyns_submod

    def test_not_defined(self):
        working_set = pkg_resources.WorkingSet([
            self.ds_egg_root,
        ])
        stub_item_attr_value(self, pkg_resources, 'working_set', working_set)
        p = indexer.resource_filename_mod_entry_point('dummyns', None)
        self.assertEqual(normcase(p), normcase(self.dummyns_path))

    def test_mismatched_ns(self):
        # mismatch includes a package that doesn't actually have the
        # directory created
        d_egg_root = join(mkdtemp(self), 'dummyns')

        make_dummy_dist(self, ((
            'namespace_packages.txt',
            'not_ns\n',
        ), (
            'entry_points.txt',
            '[dummyns]\n'
            'dummyns = dummyns:attr\n',
        ),), 'dummyns', '1.0', working_dir=d_egg_root)
        working_set = pkg_resources.WorkingSet([
            d_egg_root,
            self.ds_egg_root,
        ])
        stub_item_attr_value(self, pkg_resources, 'working_set', working_set)

        dummyns_ep = next(working_set.iter_entry_points('dummyns'))
        p = indexer.resource_filename_mod_entry_point('dummyns', dummyns_ep)
        self.assertEqual(normcase(p), normcase(self.dummyns_path))

    def test_mismatched(self):
        # mismatch includes a package that doesn't actually have the
        # directory created
        d_egg_root = join(mkdtemp(self), 'dummyns')

        make_dummy_dist(self, ((
            'namespace_packages.txt',
            'dummyns\n',
        ), (
            'entry_points.txt',
            '[dummyns]\n'
            'dummyns = dummyns:attr\n',
        ),), 'dummyns', '1.0', working_dir=d_egg_root)
        working_set = pkg_resources.WorkingSet([
            d_egg_root,
            self.ds_egg_root,
        ])
        stub_item_attr_value(self, pkg_resources, 'working_set', working_set)

        dummyns_ep = next(working_set.iter_entry_points('dummyns'))
        with pretty_logging(stream=StringIO()) as fd:
            p = indexer.resource_filename_mod_entry_point(
                'dummyns', dummyns_ep)

        self.assertIn(
            "'dummyns' resolved by entry_point 'dummyns = dummyns:attr' leads "
            "to no path", fd.getvalue()
        )
        self.assertEqual(normcase(p), normcase(self.dummyns_path))

    def test_not_namespace(self):
        d_egg_root = join(mkdtemp(self), 'dummyns')

        make_dummy_dist(self, ((
            'entry_points.txt',
            '[dummyns]\n'
            'dummyns = dummyns:attr\n',
        ),), 'dummyns', '1.0', working_dir=d_egg_root)
        working_set = pkg_resources.WorkingSet([
            d_egg_root,
            self.ds_egg_root,
        ])
        stub_item_attr_value(self, pkg_resources, 'working_set', working_set)

        moddir = join(d_egg_root, 'dummyns')
        os.makedirs(moddir)

        dummyns_ep = next(working_set.iter_entry_points('dummyns'))
        p = indexer.resource_filename_mod_entry_point('dummyns', dummyns_ep)
        self.assertEqual(normcase(p), normcase(self.dummyns_path))

    def test_standard(self):
        d_egg_root = join(mkdtemp(self), 'dummyns')

        make_dummy_dist(self, ((
            'namespace_packages.txt',
            'dummyns\n',
        ), (
            'entry_points.txt',
            '[dummyns]\n'
            'dummyns = dummyns:attr\n',
        ),), 'dummyns', '1.0', working_dir=d_egg_root)
        working_set = pkg_resources.WorkingSet([
            d_egg_root,
            self.ds_egg_root,
        ])
        stub_item_attr_value(self, pkg_resources, 'working_set', working_set)

        moddir = join(d_egg_root, 'dummyns')
        os.makedirs(moddir)

        # make this also a proper thing
        with open(join(moddir, '__init__.py'), 'w') as fd:
            fd.write('')

        dummyns_ep = next(working_set.iter_entry_points('dummyns'))
        p = indexer.resource_filename_mod_entry_point('dummyns', dummyns_ep)

        # finally, this should work.
        self.assertEqual(normcase(p), normcase(moddir))

    def test_standard_not_stubbed(self):
        d_egg_root = join(mkdtemp(self), 'dummyns')

        make_dummy_dist(self, ((
            'namespace_packages.txt',
            'dummyns\n',
        ), (
            'entry_points.txt',
            '[dummyns]\n'
            'dummyns = dummyns:attr\n',
        ),), 'dummyns', '1.0', working_dir=d_egg_root)
        working_set = pkg_resources.WorkingSet([
            d_egg_root,
            self.ds_egg_root,
        ])
        # not stubbing will result in the loader failing to actuall work

        moddir = join(d_egg_root, 'dummyns')
        os.makedirs(moddir)

        # make this also a proper thing
        with open(join(moddir, '__init__.py'), 'w') as fd:
            fd.write('')

        dummyns_ep = next(working_set.iter_entry_points('dummyns'))

        with pretty_logging(stream=StringIO()) as fd:
            p = indexer.resource_filename_mod_entry_point(
                'dummyns', dummyns_ep)

        self.assertIn(
            "resolved by entry_point 'dummyns = dummyns:attr' resulted in "
            "unexpected error", fd.getvalue()
        )

        self.assertEqual(normcase(p), normcase(self.dummyns_path))

    def test_nested_namespace(self):
        self.called = None

        def _exists(p):
            self.called = p
            return exists(p)

        working_set = pkg_resources.WorkingSet([
            self.ds_egg_root,
        ])
        stub_item_attr_value(self, pkg_resources, 'working_set', working_set)
        stub_item_attr_value(self, indexer, 'exists', _exists)

        dummyns_ep = next(working_set.iter_entry_points('dummyns.submod'))
        p = indexer.resource_filename_mod_entry_point(
            'dummyns.submod', dummyns_ep)
        self.assertEqual(p, self.called)

        with open(join(p, 'data.txt')) as fd:
            data = fd.read()

        self.assertEqual(data, self.nested_data)


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

    def test_module2_recursive_es6_legacy(self):
        # ensure legacy behavior is maintained, where a single argument
        # is accepted by the modpath function.

        def modpath_last(module):
            return indexer.modpath_last(module)

        from calmjs.testing import module2
        calmjs_base_dir = abspath(join(
            indexer.modpath_pkg_resources(indexer)[0], pardir))

        with pretty_logging(stream=StringIO()) as fd:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter('always')
                results = {
                    k: relpath(v, calmjs_base_dir)
                    for k, v in indexer.mapper(
                        module2, modpath=modpath_last,
                        globber='recursive',
                    ).items()
                }

            self.assertIn(
                "method will need to accept entry_point argument by calmjs-",
                str(w[-1].message)
            )

        self.assertIn(
            "method will need to accept entry_point argument by calmjs-",
            fd.getvalue()
        )

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

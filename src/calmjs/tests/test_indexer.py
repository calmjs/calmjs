# -*- coding: utf-8 -*-
import unittest
import os
import sys

from os.path import exists
from os.path import join
from os.path import normcase
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

# default dummy entry point for calmjs.
calmjs_ep = pkg_resources.EntryPoint.parse('demo = demo')
calmjs_ep.dist = pkg_resources.working_set.find(
    pkg_resources.Requirement.parse('calmjs'))
calmjs_dist_dir = pkg_resources.resource_filename(
    calmjs_ep.dist.as_requirement(), '')


def to_os_sep_path(p):
    # turn the given / separated path into an os specific path
    return sep.join(p.split('/'))


def rp_calmjs(mapping):
    # helper to remap all path values in the provided mapping to
    # be relative of calmjs distribution location
    return {k: relpath(v, calmjs_dist_dir) for k, v in mapping.items()}


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
        self.addCleanup(sys.modules.pop, 'dummyns')
        sys.modules['dummyns'] = dummyns

        dummyns_submod_path = join(ds_egg_root, 'dummyns', 'submod')
        dummyns_submod = ModuleType('dummyns.submod')
        dummyns_submod.__file__ = join(dummyns_submod_path, '__init__.py')
        dummyns_submod.__path__ = [dummyns_submod_path]
        self.addCleanup(sys.modules.pop, 'dummyns.submod')
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

    def test_invalid_missing_entry_point(self):
        with self.assertRaises(AttributeError):
            indexer.resource_filename_mod_entry_point('dummyns', None)

    def test_missing_distribution(self):
        d_egg_root = join(mkdtemp(self), 'dummyns')
        make_dummy_dist(self, ((
            'namespace_packages.txt',
            'not_ns\n',
        ), (
            'entry_points.txt',
            '[dummyns]\n'
            'dummyns = dummyns:attr\n',
        ),), 'dummyns', '2.0', working_dir=d_egg_root)
        working_set = pkg_resources.WorkingSet([
            d_egg_root,
            self.ds_egg_root,
        ])
        dummyns_ep = next(working_set.iter_entry_points('dummyns'))
        with pretty_logging(stream=StringIO()) as fd:
            p = indexer.resource_filename_mod_entry_point(
                'dummyns', dummyns_ep)
        # not stubbed working_set, so this is derived using fallback
        # value from the sys.modules['dummyns'] location
        self.assertEqual(normcase(p), normcase(self.dummyns_path))
        self.assertIn("distribution 'dummyns 2.0' not found", fd.getvalue())

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
        # ensure the working_set is providing the distributions being
        # mocked here so that resource_filename will resolve correctly
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

    def test_relocated_distribution(self):
        root = mkdtemp(self)
        dummyns_path = join(root, 'dummyns')

        make_dummy_dist(self, ((
            'namespace_packages.txt',
            'dummyns\n',
        ), (
            'entry_points.txt',
            '[dummyns]\n'
            'dummyns = dummyns:attr\n',
        ),), 'dummyns', '1.0', working_dir=root)
        working_set = pkg_resources.WorkingSet([
            root,
            self.ds_egg_root,
        ])
        # activate this as the working set
        stub_item_attr_value(self, pkg_resources, 'working_set', working_set)
        dummyns_ep = next(working_set.iter_entry_points('dummyns'))
        with pretty_logging(stream=StringIO()) as fd:
            p = indexer.resource_filename_mod_entry_point(
                'dummyns', dummyns_ep)
        # since the actual location is not created)
        self.assertIsNone(p)
        self.assertIn("does not exist", fd.getvalue())

        # retry with the module directory created at the expected location
        os.mkdir(dummyns_path)
        with pretty_logging(stream=StringIO()) as fd:
            p = indexer.resource_filename_mod_entry_point(
                'dummyns', dummyns_ep)
        self.assertEqual(normcase(p), normcase(dummyns_path))
        self.assertEqual('', fd.getvalue())

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
            self.assertEqual(indexer.modpath_last(module, None), [])
        self.assertIn(
            "module 'nothing' does not appear to be a namespace module",
            fd.getvalue())

    def test_get_modpath_last_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(
            indexer.modpath_last(module, None), ['/path/to/there'])

    def test_get_modpath_all_empty(self):
        module = ModuleType('nothing')
        with pretty_logging(stream=StringIO()) as fd:
            self.assertEqual(indexer.modpath_all(module, None), [])
        self.assertIn(
            "module 'nothing' does not appear to be a namespace module",
            fd.getvalue())

    def test_get_modpath_all_multi(self):
        module = ModuleType('nothing')
        module.__path__ = ['/path/to/here', '/path/to/there']
        self.assertEqual(
            indexer.modpath_all(module, None),
            ['/path/to/here', '/path/to/there'],
        )

    def test_get_modpath_pkg_resources_valid(self):
        from calmjs.testing import module3
        result = indexer.modpath_pkg_resources(module3, calmjs_ep)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].endswith(
            to_os_sep_path('calmjs/testing/module3')))

    def test_get_modpath_pkg_resources_missing_path(self):
        with pretty_logging(stream=StringIO()) as fd:
            self.assertEqual([], indexer.modpath_pkg_resources(
                None, calmjs_ep))
            self.assertIn(
                "None does not appear to be a valid module", fd.getvalue())
        with pretty_logging(stream=StringIO()) as fd:
            module = ModuleType('nothing')
            self.assertEqual([], indexer.modpath_pkg_resources(
                module, calmjs_ep))

        err = fd.getvalue()
        self.assertIn(
            "module 'nothing' and entry_point 'demo = demo'", err)
        # the input is fetched using a working entry_point, after all
        self.assertIn("resource path resolved to be '" + calmjs_dist_dir, err)
        self.assertIn("but it does not exist", fd.getvalue())

    def test_get_modpath_pkg_resources_invalid(self):
        # fake both module and entry point, which will trigger an import
        # error exception internally that gets logged.
        module = ModuleType('nothing')
        ep = pkg_resources.EntryPoint.parse('nothing = nothing')
        with pretty_logging(stream=StringIO()) as fd:
            self.assertEqual([], indexer.modpath_pkg_resources(module, ep))
        self.assertIn("module 'nothing' could not be imported", fd.getvalue())

    def test_get_modpath_pkg_resources_missing(self):
        # fake just the entry point, but provide a valid module.
        nothing = ModuleType('nothing')
        nothing.__path__ = []
        self.addCleanup(sys.modules.pop, 'nothing')
        sys.modules['nothing'] = nothing
        ep = pkg_resources.EntryPoint.parse('nothing = nothing')
        with pretty_logging(stream=StringIO()) as fd:
            self.assertEqual([], indexer.modpath_pkg_resources(nothing, ep))
        self.assertIn(
            "fail to resolve the resource path for module 'nothing' and "
            "entry_point 'nothing = nothing'", fd.getvalue())

    def test_module1_loader_es6(self):
        from calmjs.testing import module1
        results = rp_calmjs(indexer.mapper_es6(module1, calmjs_ep))
        self.assertEqual(results, {
            'calmjs/testing/module1/hello':
                to_os_sep_path('calmjs/testing/module1/hello.js'),
        })

    def test_module1_loader_python(self):
        from calmjs.testing import module1
        results = rp_calmjs(indexer.mapper_python(module1, calmjs_ep))
        self.assertEqual(results, {
            'calmjs.testing.module1.hello':
                to_os_sep_path('calmjs/testing/module1/hello.js'),
        })

    def test_module2_recursive_es6(self):
        from calmjs.testing import module2
        results = rp_calmjs(indexer.mapper(
            module2, calmjs_ep, globber='recursive'))
        self.assertEqual(results, {
            'calmjs/testing/module2/index':
                to_os_sep_path('calmjs/testing/module2/index.js'),
            'calmjs/testing/module2/helper':
                to_os_sep_path('calmjs/testing/module2/helper.js'),
            'calmjs/testing/module2/mod/helper':
                to_os_sep_path('calmjs/testing/module2/mod/helper.js'),
        })

    def test_module3_multi_path_all(self):
        """
        For modules that have multiple paths.  This is typically caused
        by specifying a module that is typically used as a namespace for
        other Python modules.  Normally this can interfere with imports
        but as long as a module is produced and the multiple path
        modpath method is used, the 'all' mapper will fulfil the order.
        """

        # See setup method for how it's built.
        module, index_js = make_multipath_module3(self)

        def join_mod3(*a):
            # use the actual value provided by the dummy module (which
            # references the real version.
            from calmjs.testing import module3
            mod3_dir = module3.__path__[0]
            return join(mod3_dir, *a)

        results = indexer.mapper(
            module, calmjs_ep, modpath='all', globber='recursive')
        self.assertEqual(results, {
            'calmjs/testing/module3/index': index_js,
            'calmjs/testing/module3/math': join_mod3('math.js'),
            'calmjs/testing/module3/mod/index': join_mod3('mod', 'index.js'),
        })

    def test_module3_multi_path_pkg_resources(self):
        """
        With the usage of pkg_resources modpath, the extra paths must be
        available somehow to this framework, but given that this is not
        setup through the framework proper the custom path provided by
        the mocked module object will never be used.
        """

        module, index_js = make_multipath_module3(self)

        def join_mod3(*a):
            return join(calmjs_dist_dir, 'calmjs', 'testing', 'module3', *a)

        results = indexer.mapper(
            module, calmjs_ep, modpath='pkg_resources', globber='recursive')
        self.assertEqual(results, {
            'calmjs/testing/module3/math': join_mod3('math.js'),
            'calmjs/testing/module3/mod/index': join_mod3('mod', 'index.js'),
        })

    def test_module2_callables(self):
        from calmjs.testing import module2
        results = rp_calmjs(indexer.mapper(
            module2,
            calmjs_ep,
            globber=indexer.globber_recursive,
            modname=indexer.modname_python,
            modpath=indexer.modpath_pkg_resources,
        ))
        self.assertEqual(results, {
            'calmjs.testing.module2.index':
                to_os_sep_path('calmjs/testing/module2/index.js'),
            'calmjs.testing.module2.helper':
                to_os_sep_path('calmjs/testing/module2/helper.js'),
            'calmjs.testing.module2.mod.helper':
                to_os_sep_path('calmjs/testing/module2/mod/helper.js'),
        })

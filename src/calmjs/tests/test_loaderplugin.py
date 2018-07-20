# -*- coding: utf-8 -*-
import unittest

from os.path import join
from os import chdir
from os import makedirs
from pkg_resources import Distribution
from pkg_resources import Requirement
from pkg_resources import resource_filename
from pkg_resources import working_set as root_working_set

import calmjs.base
from calmjs.registry import Registry
from calmjs.registry import get as root_registry_get
from calmjs.registry import _inst as root_registry
from calmjs.base import BaseLoaderPluginHandler
from calmjs.loaderplugin import LoaderPluginRegistry
from calmjs.loaderplugin import LoaderPluginHandler
from calmjs.loaderplugin import NPMLoaderPluginHandler
from calmjs.loaderplugin import ModuleLoaderRegistry
from calmjs.module import ModuleRegistry
from calmjs.toolchain import NullToolchain
from calmjs.toolchain import Spec
from calmjs.utils import pretty_logging

from calmjs.testing.utils import remember_cwd
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import stub_mod_working_set
from calmjs.testing.mocks import StringIO
from calmjs.testing.mocks import WorkingSet


class NotPlugin(LoaderPluginRegistry):
    """yeanah"""


class BadPlugin(LoaderPluginHandler):

    def __init__(self):
        """this will not be called; missing argument"""


class DupePlugin(LoaderPluginHandler):
    """
    Dummy duplicate plugin
    """


class LoaderPluginRegistryTestCase(unittest.TestCase):

    def test_to_plugin_name(self):
        registry = LoaderPluginRegistry(
            'calmjs.loader_plugin', _working_set=WorkingSet({}))
        self.assertEqual('example', registry.to_plugin_name('example'))
        self.assertEqual('example', registry.to_plugin_name('example?hi'))
        self.assertEqual('example', registry.to_plugin_name('example!hi'))
        self.assertEqual('example', registry.to_plugin_name('example?arg!hi'))

    def test_initialize_standard(self):
        # ensure that we have a proper working registry
        working_set = WorkingSet({'calmjs.loader_plugin': [
            'example = calmjs.loaderplugin:LoaderPluginHandler',
        ]})
        registry = LoaderPluginRegistry(
            'calmjs.loader_plugin', _working_set=working_set)
        plugin = registry.get('example')
        self.assertTrue(isinstance(plugin, LoaderPluginHandler))
        self.assertEqual({}, plugin.generate_handler_sourcepath(
            NullToolchain(), Spec(), {}))

    def test_initialize_failure_missing(self):
        working_set = WorkingSet({'calmjs.loader_plugin': [
            'not_plugin = calmjs.not_plugin:nothing',
        ]})
        # should not trigger import failure
        with pretty_logging(stream=StringIO()) as stream:
            registry = LoaderPluginRegistry(
                'calmjs.loader_plugin', _working_set=working_set)
        self.assertIsNone(registry.get('not_plugin'))
        self.assertIn(
            "registry 'calmjs.loader_plugin' failed to load loader plugin "
            "handler for entry point 'not_plugin =", stream.getvalue(),
        )

    def test_initialize_failure_not_plugin(self):
        working_set = WorkingSet({'calmjs.loader_plugin': [
            'not_plugin = calmjs.tests.test_loaderplugin:NotPlugin',
        ]})
        # should not trigger import failure
        with pretty_logging(stream=StringIO()) as stream:
            registry = LoaderPluginRegistry(
                'calmjs.loader_plugin', _working_set=working_set)
        self.assertIsNone(registry.get('not_plugin'))
        self.assertIn(
            "'not_plugin = calmjs.tests.test_loaderplugin:NotPlugin' does not "
            "lead to a valid loader plugin handler class",
            stream.getvalue()
        )

    def test_initialize_failure_bad_plugin(self):
        working_set = WorkingSet({'calmjs.loader_plugin': [
            'bad_plugin = calmjs.tests.test_loaderplugin:BadPlugin',
        ]}, dist=Distribution(project_name='plugin', version='1.0'))
        # should not trigger import failure
        with pretty_logging(stream=StringIO()) as stream:
            registry = LoaderPluginRegistry(
                'calmjs.loader_plugin', _working_set=working_set)
        self.assertIsNone(registry.get('bad_plugin'))
        self.assertIn(
            "registration of entry point "
            "'bad_plugin = calmjs.tests.test_loaderplugin:BadPlugin' from "
            "'plugin 1.0' to registry 'calmjs.loader_plugin' failed",
            stream.getvalue()
        )

    def test_initialize_warning_dupe_plugin(self):
        # ensure that we have a proper working registry
        working_set = WorkingSet({'calmjs.loader_plugin': [
            'example = calmjs.tests.test_loaderplugin:DupePlugin',
            'example = calmjs.loaderplugin:NPMLoaderPluginHandler',
        ]})
        # should not trigger import failure
        with pretty_logging(stream=StringIO()) as stream:
            registry = LoaderPluginRegistry(
                'calmjs.loader_plugin', _working_set=working_set)
        self.assertIn(
            "loader plugin handler for 'example' was already registered to an "
            "instance of 'calmjs.tests.test_loaderplugin:DupePlugin'",
            stream.getvalue()
        )
        # the second one will be registered
        self.assertTrue(
            isinstance(registry.get('example'), LoaderPluginHandler))
        # ensure that the handler can be acquired from a full name
        self.assertEqual('example', registry.get('example!hi').name)
        self.assertEqual('example', registry.get('example?arg!hi').name)
        self.assertEqual('example', registry.get('example?arg').name)
        self.assertIsNone(registry.get('examplearg'))
        self.assertIsNone(registry.get('ex'))
        self.assertIsNone(registry.get('ex!ample'))


class LoaderPluginHandlerTestcase(unittest.TestCase):

    def test_plugin_strip_basic(self):
        base = NPMLoaderPluginHandler(None, 'base')
        self.assertEqual(
            base.unwrap('base!some/dir/path.ext'),
            'some/dir/path.ext',
        )
        # unrelated will not be stripped.
        self.assertEqual(
            base.unwrap('something_else!some/dir/path.ext'),
            'something_else!some/dir/path.ext',
        )

    def test_plugin_unwrap_extras(self):
        base = LoaderPluginHandler(None, 'base')
        self.assertEqual(
            base.unwrap('base?someargument!some/dir/path.ext'),
            'some/dir/path.ext',
        )
        self.assertEqual(
            base.unwrap('base!other!some/dir/path.ext'),
            'other!some/dir/path.ext',
        )
        self.assertEqual(
            base.unwrap('base?arg!other?arg!some/dir/path.ext'),
            'other?arg!some/dir/path.ext',
        )

    def test_plugin_strip_edge(self):
        base = NPMLoaderPluginHandler(None, 'base')
        self.assertEqual(base.unwrap('base!'), '')

    def test_base_plugin_generate_handler_sourcepath(self):
        base = BaseLoaderPluginHandler(None, 'base')
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        self.assertEqual(
            base.generate_handler_sourcepath(toolchain, spec, {
                'base!bad': 'base!bad',
            }), {})

    def test_plugin_generate_handler_sourcepath_default_registry(self):
        base = LoaderPluginHandler(None, 'base')
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                base.generate_handler_sourcepath(toolchain, spec, {
                    'base!bad': 'base!bad',
                }), {})
        self.assertIn("using default loaderplugin registry", stream.getvalue())

    def test_plugin_generate_handler_sourcepath_resolved_registry(self):
        base = LoaderPluginHandler(None, 'base')
        reg = LoaderPluginRegistry('loaders', _working_set=WorkingSet({}))
        toolchain = NullToolchain()
        spec = Spec(
            working_dir=mkdtemp(self), calmjs_loaderplugin_registry=reg)
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                base.generate_handler_sourcepath(toolchain, spec, {
                    'base!bad': 'base!bad',
                }), {})
        self.assertIn(
            "loaderplugin registry 'loaders' already assigned to spec",
            stream.getvalue())

    def test_plugin_package_strip_broken_recursion_stop(self):
        class BadPluginHandler(LoaderPluginHandler):
            def unwrap(self, value):
                # return the identity
                return value

        base = BadPluginHandler(None, 'base')
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                base.generate_handler_sourcepath(toolchain, spec, {
                    'base!bad': 'base!bad',
                }), {})

        self.assertIn(
            "loaderplugin 'base' extracted same sourcepath of",
            stream.getvalue())

    def test_plugin_loaders_modname_source_to_target(self):
        class InterceptHandler(LoaderPluginHandler):
            def modname_source_to_target(self, *a, **kw):
                # failed to inspect and call parent
                return 'intercepted'

        reg = LoaderPluginRegistry('simloaders', _working_set=WorkingSet({}))
        base = reg.records['base'] = LoaderPluginHandler(reg, 'base')
        extra = reg.records['extra'] = LoaderPluginHandler(reg, 'extra')
        reg.records['intercept'] = InterceptHandler(reg, 'intercept')
        toolchain = NullToolchain()
        spec = Spec()
        self.assertEqual('fun.file', base.modname_source_to_target(
            toolchain, spec, 'base!fun.file', '/some/path/fun.file'))
        self.assertEqual('fun.file', extra.modname_source_to_target(
            toolchain, spec, 'extra!fun.file', '/some/path/fun.file'))
        self.assertEqual('fun.file', base.modname_source_to_target(
            toolchain, spec, 'extra!base!fun.file', '/some/path/fun.file'))
        # no plugin was found, so no modification
        self.assertEqual('noplugin!fun.file', base.modname_source_to_target(
            toolchain, spec, 'extra!noplugin!fun.file', '/some/path/fun.file'))
        # chained of the same type
        self.assertEqual('fun.file', base.modname_source_to_target(
            toolchain, spec, 'base!base!base!fun.file',
            '/some/path/fun.file'))
        # chained but overloaded
        self.assertEqual('intercepted', base.modname_source_to_target(
            toolchain, spec, 'base!intercept!base!fun.file',
            '/some/path/fun.file'))

    def test_plugin_loaders_modname_source_to_target_identity(self):
        # manually create a registry
        reg = LoaderPluginRegistry('simloaders', _working_set=WorkingSet({}))
        base = reg.records['local/dev'] = LoaderPluginHandler(reg, 'local/dev')
        toolchain = NullToolchain()
        spec = Spec()

        self.assertEqual('fun.file', base.modname_source_to_target(
            toolchain, spec, 'local/dev!fun.file',
            '/some/path/fun.file'))
        # a redundant usage test
        self.assertEqual('local/dev', base.modname_source_to_target(
            toolchain, spec, 'local/dev',
            '/some/path/to/the/plugin'))


class NPMPluginTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_plugin_base(self):
        base = NPMLoaderPluginHandler(None, 'base')
        with self.assertRaises(NotImplementedError):
            base(
                toolchain=None, spec=None, modname='', source='', target='',
                modpath='',
            )

    def test_plugin_package_base(self):
        base = NPMLoaderPluginHandler(None, 'base')
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                base.generate_handler_sourcepath(toolchain, spec, {}), {})
        self.assertIn(
            "no npm package name specified or could be resolved for "
            "loaderplugin 'base' of registry '<invalid_registry/handler>'; "
            "please subclass calmjs.loaderplugin:NPMLoaderPluginHandler such "
            "that the npm package name become specified", stream.getvalue(),
        )

    def test_plugin_package_missing_dir(self):
        base = NPMLoaderPluginHandler(None, 'base')
        base.node_module_pkg_name = 'dummy_pkg'
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                base.generate_handler_sourcepath(toolchain, spec, {}), {})
        self.assertIn(
            "could not locate 'package.json' for the npm package 'dummy_pkg' "
            "which was specified to contain the loader plugin 'base' in the "
            "current working directory '%s'" % spec['working_dir'],
            stream.getvalue(),
        )

    def test_plugin_package_missing_main(self):
        base = NPMLoaderPluginHandler(None, 'base')
        base.node_module_pkg_name = 'dummy_pkg'
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        pkg_dir = join(spec['working_dir'], 'node_modules', 'dummy_pkg')
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{}')

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                base.generate_handler_sourcepath(toolchain, spec, {}), {})

        self.assertIn(
            "calmjs.loaderplugin 'package.json' for the npm package "
            "'dummy_pkg' does not contain a valid entry point: sources "
            "required for loader plugin 'base' cannot be included "
            "automatically; the build process may fail",
            stream.getvalue(),
        )

    def test_plugin_package_success_main(self):
        base = NPMLoaderPluginHandler(None, 'base')
        base.node_module_pkg_name = 'dummy_pkg'
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        pkg_dir = join(spec['working_dir'], 'node_modules', 'dummy_pkg')
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{"main": "base.js"}')

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                join(pkg_dir, 'base.js'),
                base.generate_handler_sourcepath(toolchain, spec, {})['base'],
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())

    def test_plugin_package_success_package(self):
        base = NPMLoaderPluginHandler(None, 'base')
        base.node_module_pkg_name = 'dummy_pkg'
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        pkg_dir = join(spec['working_dir'], 'node_modules', 'dummy_pkg')
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{"browser": "browser/base.js"}')

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                join(pkg_dir, 'browser', 'base.js'),
                base.generate_handler_sourcepath(toolchain, spec, {})['base'],
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())
        self.assertNotIn("missing working_dir", stream.getvalue())

    def test_plugin_package_success_package_spec_missing_working_dir(self):
        remember_cwd(self)
        cwd = mkdtemp(self)
        chdir(cwd)

        base = NPMLoaderPluginHandler(None, 'base')
        base.node_module_pkg_name = 'dummy_pkg'
        toolchain = NullToolchain()
        spec = Spec()
        pkg_dir = join(cwd, 'node_modules', 'dummy_pkg')
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{"browser": "browser/base.js"}')

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                join(pkg_dir, 'browser', 'base.js'),
                base.generate_handler_sourcepath(toolchain, spec, {})['base'],
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())
        self.assertIn("missing working_dir", stream.getvalue())

    def test_plugin_package_dynamic_selection(self):

        class CustomHandler(NPMLoaderPluginHandler):
            def find_node_module_pkg_name(self, toolchain, spec):
                return spec.get('loaderplugin')

        reg = LoaderPluginRegistry('lp.reg', _working_set=WorkingSet({}))
        base = CustomHandler(reg, 'base')
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        pkg_dir = join(spec['working_dir'], 'node_modules', 'dummy_pkg')
        makedirs(pkg_dir)
        with open(join(pkg_dir, 'package.json'), 'w') as fd:
            fd.write('{"main": "base.js"}')

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                {}, base.generate_handler_sourcepath(toolchain, spec, {}))
        self.assertIn(
            "no npm package name specified or could be resolved for "
            "loaderplugin 'base' of registry 'lp.reg'",
            stream.getvalue()
        )
        self.assertIn(
            "test_loaderplugin:CustomHandler may be at fault",
            stream.getvalue()
        )
        self.assertNotIn("for loader plugin 'base'", stream.getvalue())

        # plug the value into the spec to satisfy the condition for this
        # particular loader

        spec['loaderplugin'] = 'dummy_pkg'
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                join(pkg_dir, 'base.js'),
                base.generate_handler_sourcepath(toolchain, spec, {})['base'],
            )
        self.assertIn("base.js' for loader plugin 'base'", stream.getvalue())

    def create_base_extra_plugins(self, working_dir):
        # manually create a registry
        reg = LoaderPluginRegistry('simloaders', _working_set=WorkingSet({}))
        base = reg.records['base'] = NPMLoaderPluginHandler(reg, 'base')
        base.node_module_pkg_name = 'dummy_pkg1'
        extra = reg.records['extra'] = NPMLoaderPluginHandler(reg, 'extra')
        extra.node_module_pkg_name = 'dummy_pkg2'

        pkg_dir1 = join(working_dir, 'node_modules', 'dummy_pkg1')
        pkg_dir2 = join(working_dir, 'node_modules', 'dummy_pkg2')
        makedirs(pkg_dir1)
        makedirs(pkg_dir2)

        with open(join(pkg_dir1, 'package.json'), 'w') as fd:
            fd.write('{"main": "base.js"}')

        with open(join(pkg_dir2, 'package.json'), 'w') as fd:
            fd.write('{"main": "extra.js"}')
        return reg, base, extra, pkg_dir1, pkg_dir2

    def test_plugin_package_chained_loaders(self):
        working_dir = mkdtemp(self)
        reg, base, extra, base_dir, extra_dir = self.create_base_extra_plugins(
            working_dir)
        # standard case
        toolchain = NullToolchain()
        spec = Spec(working_dir=working_dir)
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                {'base': join(base_dir, 'base.js')},
                base.generate_handler_sourcepath(toolchain, spec, {
                    'base!fun.file': 'base!fun.file',
                }),
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual({
                'base': join(base_dir, 'base.js'),
                'extra': join(extra_dir, 'extra.js'),
            }, base.generate_handler_sourcepath(toolchain, spec, {
                    'base!fun.file': 'fun.file',
                    'base!extra!fun.file': 'fun.file',
                    'base!missing!fun.file': 'fun.file',
                    'base!extra!missing!fun.file': 'fun.file',
                }),
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())
        self.assertIn("for loader plugin 'extra'", stream.getvalue())
        self.assertNotIn("for loader plugin 'missing'", stream.getvalue())

        # for the outer one
        self.assertIn(
            "loaderplugin 'base' from registry 'simloaders' cannot find "
            "sibling loaderplugin handler for 'missing'; processing may fail "
            "for the following nested/chained sources: "
            "{'missing!fun.file': 'fun.file'}", stream.getvalue()
        )
        # for the inner one
        self.assertIn(
            "loaderplugin 'extra' from registry 'simloaders' cannot find "
            "sibling loaderplugin handler for 'missing'; processing may fail "
            "for the following nested/chained sources: "
            "{'missing!fun.file': 'fun.file'}", stream.getvalue()
        )

        # for repeat loaders
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual({
                'base': join(base_dir, 'base.js'),
                'extra': join(extra_dir, 'extra.js'),
            }, base.generate_handler_sourcepath(toolchain, spec, {
                    'base!extra!base!extra!fun.file': 'fun.file',
                }),
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())
        self.assertIn("for loader plugin 'extra'", stream.getvalue())

        # for repeat loaders
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual({
                'base': join(base_dir, 'base.js'),
            }, base.generate_handler_sourcepath(toolchain, spec, {
                    'base!base!base!fun.file': 'fun.file',
                }),
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())

        # for argument loaders
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual({
                'base': join(base_dir, 'base.js'),
                'extra': join(extra_dir, 'extra.js'),
            }, base.generate_handler_sourcepath(toolchain, spec, {
                    'base?argument!extra?argument!fun.file': 'fun.file',
                }),
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())
        self.assertIn("for loader plugin 'extra'", stream.getvalue())

    def test_plugin_package_chained_loaders_initial_simple(self):
        working_dir = mkdtemp(self)
        reg, base, extra, base_dir, extra_dir = self.create_base_extra_plugins(
            working_dir)
        simple = reg.records['simple'] = LoaderPluginHandler(reg, 'simple')

        toolchain = NullToolchain()
        spec = Spec(working_dir=working_dir)

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                {},
                simple.generate_handler_sourcepath(toolchain, spec, {
                    'simple!fun.file': 'fun.file',
                }),
            )

        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual({
                'extra': join(extra_dir, 'extra.js'),
            }, simple.generate_handler_sourcepath(toolchain, spec, {
                    'simple!extra!fun.file': 'fun.file',
                }),
            )
        self.assertIn("for loader plugin 'extra'", stream.getvalue())

    def test_plugin_loaders_modname_source_to_target(self):
        working_dir = mkdtemp(self)
        reg, base, extra, base_dir, extra_dir = self.create_base_extra_plugins(
            working_dir)
        toolchain = NullToolchain()
        spec = Spec(working_dir=working_dir)
        self.assertEqual('fun.file', base.modname_source_to_target(
            toolchain, spec, 'base!fun.file', '/some/path/fun.file'))
        self.assertEqual('fun.file', base.modname_source_to_target(
            toolchain, spec, 'extra!base!fun.file', '/some/path/fun.file'))
        # no plugin was found, so no modification
        self.assertEqual('noplugin!fun.file', base.modname_source_to_target(
            toolchain, spec, 'extra!noplugin!fun.file', '/some/path/fun.file'))
        # chained of the same type
        self.assertEqual('fun.file', base.modname_source_to_target(
            toolchain, spec, 'base!base!base!fun.file',
            '/some/path/fun.file'))
        # a mismatched test


class ModuleLoaderRegistryTestCase(unittest.TestCase):
    """
    Test the module loader registry with a mocked working set with
    actual data to see resolution through the system.
    """

    def test_manual_construction_invalid_suffix_fail(self):
        with self.assertRaises(ValueError) as e:
            ModuleLoaderRegistry('some.module', _working_set=WorkingSet({}))
        self.assertEqual(
            "child module registry name defined with invalid suffix "
            "('some.module' does not end with '.loader')", str(e.exception))

    def test_manual_construction_parent_interactions(self):
        self.assertTrue(ModuleLoaderRegistry(
            'calmjs.module.loader', _working_set=WorkingSet({})))

        # forcibly stub out the real calmjs.module
        self.addCleanup(root_registry.records.pop, 'calmjs.module')
        root_registry.records['calmjs.module'] = None

        with self.assertRaises(ValueError) as e:
            ModuleLoaderRegistry(
                'calmjs.module.loader', _working_set=WorkingSet({}))
        self.assertEqual(
            "could not construct child module registry 'calmjs.module.loader' "
            "as its parent registry 'calmjs.module' could not be found",
            str(e.exception)
        )

    def test_module_loader_registry_integration(self):
        working_set = WorkingSet({
            'calmjs.module': [
                'module4 = calmjs.testing.module4',
            ],
            'calmjs.module.loader': [
                'css = css[style]',
            ],
            __name__: [
                'calmjs.module = calmjs.module:ModuleRegistry',
                'calmjs.module.loader = '
                'calmjs.loaderplugin:ModuleLoaderRegistry',
            ]},
            dist=Distribution(project_name='calmjs.testing', version='0.0')
        )
        stub_mod_working_set(self, [calmjs.base], working_set)

        # Not going to use the global registry, and using our custom
        # reservation entry
        local_root_registry = Registry(
            __name__, 'calmjs.testing', _working_set=working_set)

        with pretty_logging(stream=StringIO()):
            # silences "distribution 'calmjs.testing 0.0' not found"
            # warnings from stdout produced by the indexer, as the
            # provided working_set is invalid with entry points that do
            # not have a valid distribution.
            module_registry = root_registry_get('calmjs.module')
            module_loader_registry = root_registry_get('calmjs.module.loader')
            registry = local_root_registry.get_record('calmjs.module')
            loader_registry = local_root_registry.get_record(
                'calmjs.module.loader')

        self.assertIsNot(registry, module_registry)
        self.assertIsNot(loader_registry, module_loader_registry)
        self.assertEqual(
            sorted(k for k, v in registry.iter_records()), [
                'calmjs.testing.module4',
            ]
        )

        # test the basic items.
        results = registry.get_records_for_package('calmjs.testing')
        self.assertEqual(sorted(results.keys()), [
           'calmjs/testing/module4/widget',
        ])

        module4 = registry.get_record('calmjs.testing.module4')
        self.assertIn('calmjs/testing/module4/widget', module4)

        self.assertEqual({
            'css!calmjs/testing/module4/widget.style': resource_filename(
                'calmjs.testing', join('module4', 'widget.style')),
        }, loader_registry.get_records_for_package('calmjs.testing'))

        self.assertEqual(
            ['css'],
            loader_registry.get_loaders_for_package('calmjs.testing')
        )

    def test_module_loader_registry_multiple_loaders(self):
        working_set = WorkingSet({
            'calmjs.module': [
                'module4 = calmjs.testing.module4',
            ],
            'calmjs.module.loader': [
                'css = css[style,css]',
                'json = json[json]',
                'empty = empty[]',
            ],
            __name__: [
                'calmjs.module = calmjs.module:ModuleRegistry',
                'calmjs.module.loader = '
                'calmjs.loaderplugin:ModuleLoaderRegistry',
            ]},
            # use a real distribution instead for this case
            dist=root_working_set.find(Requirement.parse('calmjs')),
        )

        registry = ModuleRegistry('calmjs.module', _working_set=working_set)
        loader_registry = ModuleLoaderRegistry(
            'calmjs.module.loader', _working_set=working_set, _parent=registry)
        self.assertEqual({
            'calmjs': ['calmjs.testing.module4'],
        }, loader_registry.package_module_map)

        self.assertEqual(
            ['css', 'empty', 'json'],
            sorted(loader_registry.get_loaders_for_package('calmjs'))
        )

        self.assertEqual([
            'css!calmjs/testing/module4/other.css',
            'css!calmjs/testing/module4/widget.style',
            'json!calmjs/testing/module4/data.json',
        ], sorted(loader_registry.get_records_for_package('calmjs').keys()))

        # was not registered to calmjs.testing
        self.assertEqual([], loader_registry.get_loaders_for_package(
            'calmjs.testing'))
        self.assertEqual({}, loader_registry.get_records_for_package(
            'calmjs.testing'))

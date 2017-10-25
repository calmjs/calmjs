# -*- coding: utf-8 -*-
import unittest

from os.path import join
from os import chdir
from os import makedirs

from calmjs.loaderplugin import LoaderPluginRegistry
from calmjs.loaderplugin import BaseLoaderPluginHandler
from calmjs.loaderplugin import NPMLoaderPluginHandler
from calmjs.toolchain import NullToolchain
from calmjs.toolchain import Spec
from calmjs.utils import pretty_logging

from calmjs.testing.utils import remember_cwd
from calmjs.testing.utils import mkdtemp
from calmjs.testing.mocks import StringIO
from calmjs.testing.mocks import WorkingSet


class NotPlugin(LoaderPluginRegistry):
    """yeanah"""


class BadPlugin(BaseLoaderPluginHandler):

    def __init__(self):
        """this will not be called; missing argument"""


class DupePlugin(BaseLoaderPluginHandler):
    """
    Dummy duplicate plugin
    """


class LoaderPluginRegistryTestCase(unittest.TestCase):

    def test_initialize_standard(self):
        # ensure that we have a proper working registry
        working_set = WorkingSet({'calmjs.loader_plugin': [
            'example = calmjs.loaderplugin:BaseLoaderPluginHandler',
        ]})
        registry = LoaderPluginRegistry(
            'calmjs.loader_plugin', _working_set=working_set)
        plugin = registry.get('example')
        self.assertTrue(isinstance(plugin, BaseLoaderPluginHandler))
        self.assertEqual(
            {}, plugin.locate_bundle_sourcepath(NullToolchain(), Spec(), {}))

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
        ]})
        # should not trigger import failure
        with pretty_logging(stream=StringIO()) as stream:
            registry = LoaderPluginRegistry(
                'calmjs.loader_plugin', _working_set=working_set)
        self.assertIsNone(registry.get('bad_plugin'))
        self.assertIn(
            "the loader plugin class registered at 'bad_plugin = "
            "calmjs.tests.test_loaderplugin:BadPlugin' failed "
            "to be instantiated with the following exception",
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
            isinstance(registry.get('example'), BaseLoaderPluginHandler))


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

    def test_plugin_strip(self):
        base = NPMLoaderPluginHandler(None, 'base')
        self.assertEqual(
            base.strip_plugin('base!some/dir/path.ext'),
            'some/dir/path.ext',
        )
        # unrelated will not be stripped.
        self.assertEqual(
            base.strip_plugin('something_else!some/dir/path.ext'),
            'something_else!some/dir/path.ext',
        )

    def test_plugin_package_base(self):
        base = NPMLoaderPluginHandler(None, 'base')
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        self.assertEqual(
            base.locate_bundle_sourcepath(toolchain, spec, {}), {})

    def test_plugin_package_missing_dir(self):
        base = NPMLoaderPluginHandler(None, 'base')
        base.node_module_pkg_name = 'dummy_pkg'
        toolchain = NullToolchain()
        spec = Spec(working_dir=mkdtemp(self))
        with pretty_logging(stream=StringIO()) as stream:
            self.assertEqual(
                base.locate_bundle_sourcepath(toolchain, spec, {}), {})
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
                base.locate_bundle_sourcepath(toolchain, spec, {}), {})

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
                base.locate_bundle_sourcepath(toolchain, spec, {})['base'],
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
                base.locate_bundle_sourcepath(toolchain, spec, {})['base'],
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
                base.locate_bundle_sourcepath(toolchain, spec, {})['base'],
            )
        self.assertIn("for loader plugin 'base'", stream.getvalue())
        self.assertIn("missing working_dir", stream.getvalue())

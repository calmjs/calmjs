# -*- coding: utf-8 -*-
import unittest
import sys
import tempfile
import warnings

from pkg_resources import WorkingSet
from pkg_resources import Requirement

import os
from os.path import exists
from os.path import join
from os.path import normcase
from os.path import realpath
from shutil import rmtree

from calmjs.testing import utils
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import mkdtemp_singleton
from calmjs.testing.utils import make_dummy_dist


class MockTempfile(object):

    def __init__(self):
        self.count = 0
        self.dirs = []

    def mkdtemp(self):
        self.count += 1
        result = realpath(tempfile.mkdtemp())
        self.dirs.append(result)
        return result

    def cleanup(self):
        for p in self.dirs:
            if exists(p):
                rmtree(p)


class BootstrapTestingUtilsTestCase(unittest.TestCase):
    """
    These BETTER work.
    """

    def setUp(self):
        self.tmpdir = realpath(tempfile.mkdtemp())
        tempfile.tempdir = self.tmpdir

    def tearDown(self):
        # This is safe - the module will just call gettempdir() again
        tempfile.tempdir = None
        rmtree(self.tmpdir)

    def test_mock_tempfile(self):
        mock_tempfile = MockTempfile()
        mock_tempfile.mkdtemp()
        self.assertEqual(mock_tempfile.count, 1)
        self.assertTrue(exists(mock_tempfile.dirs[0]))
        # If this is NOT true, we probably left tmpdirs around.
        self.assertTrue(mock_tempfile.dirs[0].startswith(self.tmpdir))
        mock_tempfile.cleanup()
        self.assertFalse(exists(mock_tempfile.dirs[0]))


class TestingUtilsTestCase(unittest.TestCase):
    """
    Some basic harness test case.
    """

    def setUp(self):
        # Set up the simple mock for counting the number of times the
        # mkdtemp call has been made from the testing utils module.
        self.mock_tempfile = MockTempfile()
        utils.tempfile, self.old_tempfile = self.mock_tempfile, utils.tempfile

    def tearDown(self):
        self.mock_tempfile.cleanup()
        utils.tempfile = self.old_tempfile

    def test_rmtree_test(self):
        path = mkdtemp(self)
        utils.rmtree(path)
        self.assertFalse(exists(path))
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            utils.rmtree(path)
            self.assertFalse(w)

        utils.stub_item_attr_value(
            self, utils, 'rmtree_', utils.fake_error(IOError))
        path2 = mkdtemp(self)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            utils.rmtree(path2)
            self.assertIn("rmtree failed to remove", str(w[-1].message))

    def test_rmtree_win32(self):
        utils.stub_item_attr_value(self, sys, 'platform', 'win32')
        removed = []

        def fake_rmtree(path):
            removed.append(path)
            raise IOError('fake')

        utils.stub_item_attr_value(self, utils, 'rmtree_', fake_rmtree)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter('always')
            utils.rmtree('C:\\Windows')
        self.assertEqual(removed, ['C:\\Windows', '\\\\?\\C:\\Windows'])

    def test_mkdtemp_not_test(self):
        with self.assertRaises(TypeError):
            mkdtemp(object)
        self.assertEqual(self.mock_tempfile.count, 0)

    def test_mkdtemp_missing_addcleanup(self):
        # Quick and dirty subclassing for type signature and cleanup
        # availability sanity checks.
        FakeTestCase = type('FakeTestCase', (unittest.TestCase,), {
            'runTest': None,
            'addCleanup': None,
        })
        with self.assertRaises(TypeError):
            mkdtemp(FakeTestCase())

        self.assertEqual(self.mock_tempfile.count, 0)

    def test_mkdtemp_clean_ups(self):
        target1 = mkdtemp(self)
        target2 = mkdtemp(self)
        self.assertTrue(exists(target1))
        self.assertTrue(exists(target2))
        self.assertNotEqual(target1, target2)
        self.doCleanups()
        self.assertFalse(exists(target1))
        self.assertFalse(exists(target2))
        self.assertEqual(self.mock_tempfile.count, 2)

    def test_mkdtemp_singleton_clean_ups(self):
        target = mkdtemp_singleton(self)
        repeated = mkdtemp_singleton(self)
        self.assertTrue(exists(target))
        self.assertEqual(target, repeated)  # same dir returned.
        self.assertEqual(self.mock_tempfile.count, 1)  # called once.
        self.assertEqual(self._calmjs_testing_tmpdir, target)
        self.doCleanups()
        self.assertFalse(exists(target))
        self.assertFalse(hasattr(self, '_calmjs_testing_tmpdir'))

        # pretend we go into a different scope
        new_target = mkdtemp_singleton(self)
        # The next test should of course have a new directory.
        self.assertNotEqual(target, new_target)
        self.doCleanups()
        self.assertFalse(exists(new_target))
        self.assertFalse(hasattr(self, '_calmjs_testing_tmpdir'))

    def test_create_fake_bin(self):
        path = mkdtemp(self)
        program = utils.create_fake_bin(path, 'program')
        self.assertTrue(exists(program))
        self.assertIn('program', program)
        # Further, more actual testing will be done in test modules

    def tests_make_dummy_dist(self):
        target = make_dummy_dist(  # noqa: F841
            self, (
                ('dummyinfo', 'hello world'),
                ('fakeinfo', 'these are actually metadata'),
            ), 'fakepkg', '0.999')

        fn = join(
            self._calmjs_testing_tmpdir, 'fakepkg-0.999.egg-info', 'dummyinfo')
        with open(fn) as fd:
            result = fd.read()
        self.assertEqual(result, 'hello world')

        fn = join(
            self._calmjs_testing_tmpdir, 'fakepkg-0.999.egg-info', 'fakeinfo')
        with open(fn) as fd:
            result = fd.read()
        self.assertEqual(result, 'these are actually metadata')

    def tests_make_dummy_dist_working_set(self):
        """
        Dummy distributions should work with pkg_resources.WorkingSet
        """

        # This also shows how WorkingSet might work.
        # A WorkingSet is basically a way to get to a collection of
        # distributions via the list of specified paths.  By default it
        # will go for sys.path, but for testing purposes we can control
        # this by creating our own instance on a temporary directory.

        parentpkg = make_dummy_dist(self, (  # noqa: F841
            ('requires.txt', '\n'.join([
            ])),
        ), 'parentpkg', '0.8')

        childpkg = make_dummy_dist(self, (  # noqa: F841
            ('requires.txt', '\n'.join([
                'parentpkg>=0.8',
            ])),
        ), 'childpkg', '0.1')

        grandchildpkg = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'childpkg>=0.1',
                'parentpkg>=0.8',
            ])),
        ), 'grandchildpkg', '0.8')

        working_set = WorkingSet([self._calmjs_testing_tmpdir])
        distributions = working_set.resolve(grandchildpkg.requires())
        self.assertEqual(len(distributions), 2)
        self.assertEqual(distributions[0].requires(), [])
        self.assertEqual(distributions[1].requires(), [
            Requirement.parse('parentpkg>=0.8')])

        # overwrite should work
        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'parentpkg>=0.7',
            ])),
        ), 'childpkg', '0.1')
        # but the data have to be recreated
        working_set = WorkingSet([self._calmjs_testing_tmpdir])
        distributions = working_set.resolve(grandchildpkg.requires())
        self.assertEqual(distributions[1].requires(), [
            Requirement.parse('parentpkg>=0.7')])

    def tests_instantiate_integration_registries(self):
        """
        Ensure that the integration registries, specifically the root
        registry, be instantiated (or re-instantiated) in a way that
        satisfies expectations of integration test creators.
        """

        make_dummy_dist(self, (
            ('entry_points.txt', '\n'.join([
                '[calmjs.registry]',
                'dummy.module = calmjs.module:ModuleRegistry',
                'other.module = calmjs.module:ModuleRegistry',
            ])),
        ), 'somepkg', '1.0')

        working_set = WorkingSet([self._calmjs_testing_tmpdir])
        registry = utils.instantiate_integration_registries(
            working_set, None,
            'dummy.module',
        )
        dummy_module = registry.get('dummy.module')
        other_module = registry.get('other.module')
        self.assertEqual('dummy.module', dummy_module.registry_name)
        self.assertIsNone(registry.get('dummy.module.tests'))

        make_dummy_dist(self, (
            ('entry_points.txt', '\n'.join([
                '[calmjs.registry]',
                'dummy.module.tests = calmjs.module:ModuleRegistry',
            ])),
        ), 'somepkg.testing', '1.0')
        # re-add the tmpdir to reinitialize the working set with the
        # newly added entry points
        working_set.add_entry(self._calmjs_testing_tmpdir)

        reinstantiated_registry = utils.instantiate_integration_registries(
            working_set, registry,
            'dummy.module',
            'dummy.module.tests',
        )
        # ensure that it is the same instance, as this could be used to
        # reinstantiate the registry with the additional entries.
        self.assertIs(registry, reinstantiated_registry)
        # the inner registries should be renewed.
        self.assertIsNot(dummy_module, registry.get('dummy.module'))
        # the not reinstantiated version is not renewed
        self.assertIs(other_module, registry.get('other.module'))
        # the newly added entry points should resolve now.
        self.assertIsNotNone(registry.get('dummy.module.tests'))

    # both of these incidentally will test mkdtemp's behavior with chdir
    # inside windows, too.

    def test_remember_cwd_mkdtemp(self):
        cwd = os.getcwd()
        # must be done in this order as the cleanups are done FILO.
        utils.remember_cwd(self)
        tmpdir = mkdtemp(self)
        # this will mean that cwd would normally be in tmpdir before
        # the cwd cleanup gets called.
        os.chdir(tmpdir)
        self.assertNotEqual(cwd, os.getcwd())
        self.doCleanups()
        self.assertEqual(cwd, os.getcwd())

    def test_remember_cwd_mkdtemp_chdir_deep(self):
        cwd = os.getcwd()
        utils.remember_cwd(self)
        tmpdir = mkdtemp(self)
        newdir = join(tmpdir, 'some', 'nested', 'dir')
        os.makedirs(newdir)
        os.chdir(newdir)
        self.assertNotEqual(cwd, os.getcwd())

        self.doCleanups()
        self.assertEqual(cwd, os.getcwd())

    def test_stub_item_attr_value(self):
        marker = object()

        class Dummy(object):
            foo = marker

        utils.stub_item_attr_value(self, Dummy, 'foo', None)
        self.assertIsNone(Dummy.foo)
        self.doCleanups()
        self.assertIs(Dummy.foo, marker)

    def test_stub_base_which(self):
        from calmjs import base
        utils.stub_base_which(self)
        _marker = object()
        self.assertIs(base.which(_marker), _marker)
        self.doCleanups()

        _alternative = object()
        utils.stub_base_which(self, _alternative)
        _marker = object()
        self.assertIs(base.which(_marker), _alternative)
        self.doCleanups()

    def test_stub_check_interactive(self):
        from calmjs import ui
        original = ui.check_interactive
        self.assertIs(ui.check_interactive, original)
        utils.stub_check_interactive(self, None)
        self.assertIsNot(ui.check_interactive, original)
        # it now returns this typically invalid result for testing
        self.assertIsNone(ui.check_interactive())
        self.doCleanups()
        self.assertIs(ui.check_interactive, original)

    def test_stub_mod_check_interactive(self):
        from calmjs import ui
        from calmjs import cli
        original = ui.check_interactive
        self.assertIs(ui.check_interactive, original)
        utils.stub_mod_check_interactive(self, [cli], None)
        self.assertIsNot(ui.check_interactive, original)
        # it now returns this typically invalid result for testing
        self.assertIsNone(ui.check_interactive())
        self.doCleanups()
        self.assertIs(ui.check_interactive, original)

    def test_stub_mod_working_set(self):
        from calmjs import base
        original_working_set = base.working_set
        self.assertIsNot(base.working_set, None)
        utils.stub_mod_working_set(self, [base], None)
        self.assertIs(base.working_set, None)
        self.doCleanups()
        self.assertIs(base.working_set, original_working_set)

    def test_stub_os_environ(self):
        self.assertNotEqual(os.environ['PATH'], '')
        original = os.environ['PATH']
        utils.stub_os_environ(self)
        os.environ['PATH'] = ''
        self.assertNotEqual(os.environ['PATH'], original)
        self.doCleanups()
        self.assertEqual(os.environ['PATH'], original)

    def test_stub_stdin(self):
        o_stdin = sys.stdin
        utils.stub_stdin(self, u'N')
        self.assertIsNot(o_stdin, sys.stdin)
        self.assertEqual(sys.stdin.getvalue(), u'N')
        self.doCleanups()
        self.assertIs(o_stdin, sys.stdin)

    def test_stub_stdouts(self):
        o_stdout = sys.stdout
        o_stderr = sys.stderr
        utils.stub_stdouts(self)
        self.assertIsNot(o_stdout, sys.stdout)
        self.assertIsNot(o_stderr, sys.stderr)
        self.doCleanups()
        self.assertIs(o_stdout, sys.stdout)
        self.assertIs(o_stderr, sys.stderr)


class IntegrationGeneratorTestCase(unittest.TestCase):
    """
    Just to put this separate from the rest, as this tests the creation
    of an integration working set for use by other tools integrating
    calmjs for their integration testing.

    The testing utils better be working already.
    """

    def setUp(self):
        # Again setting up this mock for safety (and laziness) while
        # testing.
        self.mock_tempfile = MockTempfile()
        utils.tempfile, self.old_tempfile = self.mock_tempfile, utils.tempfile
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)
        self.mock_tempfile.cleanup()
        utils.tempfile = self.old_tempfile

    def test_integration_generator(self):
        from calmjs import base

        tmpdir = mkdtemp(self)
        # acquire some module from the internal API for subsequent
        # validation of proper cleanup.
        module = base._import_module('calmjs')
        results = utils.generate_integration_environment(working_dir=tmpdir)

        # ensure the original method is done.
        self.assertIs(base._import_module('calmjs'), module)

        working_set, registry, loader_registry, test_registry = results
        # validate the underlying information
        self.assertEqual(sorted(registry.records.keys()), [
            'forms', 'framework', 'service', 'service.rpc', 'widget',
        ])
        self.assertEqual(sorted(registry.package_module_map.keys()), [
            'forms', 'framework', 'service', 'widget',
        ])
        self.assertEqual(sorted(registry.package_module_map['service']), [
            'service', 'service.rpc',
        ])

        # TODO do some assertion on loader_registry

        # test registry will be empty until there is a standardized way
        # of doing testing in JavaScript, since the tests supplied may
        # likely not work with whatever (at least until a Python package
        # that will provide the JavaScript test framework).
        self.assertEqual(sorted(test_registry.records.keys()), [])

        # Test out the registry
        service_records = registry.get_records_for_package('service')
        self.assertEqual(len(service_records), 2)
        self.assertTrue(exists(service_records['service/rpc/lib']))
        self.assertTrue(service_records['service/rpc/lib'].endswith(
            join('service', 'rpc', 'lib.js')))
        self.assertTrue(
            normcase(service_records['service/rpc/lib']).startswith(
                normcase(tmpdir)))
        self.assertTrue(service_records['service/endpoint'].endswith(
            join('service', 'endpoint.js')))
        self.assertTrue(
            normcase(service_records['service/endpoint']).startswith(
                normcase(tmpdir)))

        # Test out the working set
        framework_dist = working_set.find(Requirement.parse('framework'))
        self.assertEqual(framework_dist.project_name, 'framework')
        self.assertEqual(normcase(framework_dist.location), normcase(tmpdir))

        self.assertTrue(exists(
            join(tmpdir, 'fake_modules', 'jquery', 'dist', 'jquery.js')))
        self.assertTrue(exists(
            join(tmpdir, 'fake_modules', 'underscore', 'underscore.js')))

    def test_integration_setup_and_teardown(self):
        from calmjs.registry import get
        # See that the standard registry has what we expected
        std_extra_keys = list(get('calmjs.extras_keys').iter_records())
        self.assertNotEqual(std_extra_keys, ['fake_modules'])
        self.assertIn('node_modules', std_extra_keys)

        self.assertIn('node_modules', std_extra_keys)
        TestCase = type('TestCase', (unittest.TestCase,), {})
        utils.setup_class_integration_environment(TestCase)
        self.assertIn(TestCase.dist_dir, self.mock_tempfile.dirs)
        registry = get('calmjs.registry')
        self.assertEqual(TestCase.registry_name, 'calmjs.module.simulated')
        self.assertTrue(registry.get('calmjs.module.simulated'))
        # works using the global function
        self.assertTrue(get('calmjs.module.simulated'))

        # See that the registry fake_modules actually got registered
        extra_keys = list(get('calmjs.extras_keys').iter_records())
        self.assertIn('fake_modules', extra_keys)

        utils.teardown_class_integration_environment(TestCase)
        # the mock registry is unchanged
        self.assertTrue(registry.get('calmjs.module.simulated'))
        # global changes should no longer be in effect.
        self.assertIsNone(get('calmjs.module.simulated'))
        self.assertFalse(exists(TestCase.dist_dir))

        # See that the registry fake_modules actually got registered
        std_extra_keys = list(get('calmjs.extras_keys').iter_records())
        self.assertNotEqual(std_extra_keys, ['fake_modules'])
        self.assertIn('node_modules', std_extra_keys)

    def test_setup_class_install_environment_failure(self):
        from calmjs.base import BaseDriver

        TestCase = type('TestCase', (unittest.TestCase,), {})
        with self.assertRaises(TypeError):
            utils.setup_class_install_environment(TestCase, BaseDriver, [])

        # shouldn't create the temporary directory as this should
        # completely abort the operation (which prevents the cleanup
        # from even firing).
        self.assertEqual(self.mock_tempfile.count, 0)

    def test_setup_class_install_environment_install(self):
        from calmjs import cli
        from calmjs.npm import Driver

        utils.stub_mod_call(self, cli)
        utils.stub_base_which(self, 'npm')
        utils.stub_os_environ(self)
        os.environ.pop('CALMJS_TEST_ENV', '')

        cwd = os.getcwd()
        TestCase = type('TestCase', (unittest.TestCase,), {})
        utils.setup_class_install_environment(
            TestCase, Driver, ['dummy_package'])
        self.assertEqual(self.mock_tempfile.count, 1)
        self.assertNotEqual(TestCase._env_root, cwd)
        self.assertEqual(TestCase._env_root, TestCase._cls_tmpdir)
        self.assertTrue(exists(join(TestCase._env_root, 'package.json')))
        p, kw = self.call_args
        self.assertEqual(p, (['npm', 'install'],))
        self.assertEqual(kw['cwd'], TestCase._cls_tmpdir)

    def test_setup_class_install_environment_predefined_no_dir(self):
        from calmjs.cli import PackageManagerDriver
        from calmjs import cli

        utils.stub_os_environ(self)
        utils.stub_mod_call(self, cli)
        cwd = mkdtemp(self)
        # we have the mock_tempfile context...
        self.assertEqual(self.mock_tempfile.count, 1)
        os.chdir(cwd)

        # a very common use case
        os.environ['CALMJS_TEST_ENV'] = '.'
        TestCase = type('TestCase', (unittest.TestCase,), {})
        # the directory not there.
        with self.assertRaises(unittest.SkipTest):
            utils.setup_class_install_environment(
                TestCase, PackageManagerDriver, [])
        # temporary directory should not be created as the skip will
        # also stop the teardown from running
        self.assertEqual(self.mock_tempfile.count, 1)
        # this is still set, but irrelevant.
        self.assertEqual(TestCase._env_root, cwd)
        # tmpdir not set.
        self.assertFalse(hasattr(TestCase, '_cls_tmpdir'))

    def test_setup_class_install_environment_predefined_success(self):
        from calmjs.cli import PackageManagerDriver
        from calmjs import cli

        utils.stub_os_environ(self)
        utils.stub_mod_call(self, cli)
        cwd = mkdtemp(self)
        # we have the mock_tempfile context...
        self.assertEqual(self.mock_tempfile.count, 1)
        os.chdir(cwd)

        os.environ['CALMJS_TEST_ENV'] = '.'
        TestCase = type('TestCase', (unittest.TestCase,), {})
        # the directory now provided..
        os.mkdir(join(cwd, 'node_modules'))
        utils.setup_class_install_environment(
            TestCase, PackageManagerDriver, [])
        # temporary directory created nonetheless
        self.assertEqual(self.mock_tempfile.count, 2)
        self.assertEqual(TestCase._env_root, cwd)
        self.assertNotEqual(TestCase._env_root, TestCase._cls_tmpdir)

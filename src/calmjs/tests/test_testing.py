# -*- coding: utf-8 -*-
import unittest
import sys
import tempfile

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

    def test_stub_mod_check_interactive(self):
        from calmjs import cli
        original = cli.check_interactive
        self.assertIs(cli.check_interactive, original)
        utils.stub_mod_check_interactive(self, [cli], None)
        self.assertIsNot(cli.check_interactive, original)
        # it now returns this typically invalid result for testing
        self.assertIsNone(cli.check_interactive())
        self.doCleanups()
        self.assertIs(cli.check_interactive, original)

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
        # Again setting up this mock for safety while testing.
        self.mock_tempfile = MockTempfile()
        utils.tempfile, self.old_tempfile = self.mock_tempfile, utils.tempfile

    def tearDown(self):
        self.mock_tempfile.cleanup()
        utils.tempfile = self.old_tempfile

    def test_integration_generator(self):
        tmpdir = mkdtemp(self)
        results = utils.generate_integration_environment(working_dir=tmpdir)
        working_set, registry = results
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

        # Test out the registry
        service_records = registry.get_records_for_package('service')
        self.assertEqual(len(service_records), 2)
        self.assertTrue(exists(service_records['service/rpc/lib']))
        self.assertTrue(service_records['service/rpc/lib'].endswith(
            join('service', 'rpc', 'lib.js')))
        self.assertTrue(service_records['service/rpc/lib'].startswith(tmpdir))
        self.assertTrue(service_records['service/endpoint'].endswith(
            join('service', 'endpoint.js')))
        self.assertTrue(service_records['service/endpoint'].startswith(tmpdir))

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

        # See that the registry fake_modules actually got registered
        extra_keys = list(get('calmjs.extras_keys').iter_records())
        self.assertEqual(extra_keys, ['fake_modules'])

        utils.teardown_class_integration_environment(TestCase)
        self.assertIsNone(registry.get('calmjs.module.simulated'))
        self.assertFalse(exists(TestCase.dist_dir))

        # See that the registry fake_modules actually got registered
        std_extra_keys = list(get('calmjs.extras_keys').iter_records())
        self.assertNotEqual(std_extra_keys, ['fake_modules'])
        self.assertIn('node_modules', std_extra_keys)

# -*- coding: utf-8 -*-
import unittest
import sys
import tempfile

from pkg_resources import WorkingSet
from pkg_resources import Requirement

import os
from os.path import exists
from os.path import join

from calmjs.testing import utils
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import mkdtemp_singleton
from calmjs.testing.utils import make_dummy_dist


class MockTempfile(object):

    def __init__(self):
        self.count = 0

    def mkdtemp(self):
        self.count += 1
        return tempfile.mkdtemp()


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
        utils.tempfile = self.old_tempfile

    def test_mkdtemp_not_test(self):
        with self.assertRaises(TypeError):
            mkdtemp(object)

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

    def test_remember_cwd(self):
        cwd = os.getcwd()
        utils.remember_cwd(self)
        os.chdir(mkdtemp(self))
        self.assertNotEqual(cwd, os.getcwd())
        self.doCleanups()
        self.assertEqual(cwd, os.getcwd())

    def test_stub_dist_flatten_egginfo_json(self):
        from calmjs import dist
        original = dist.flatten_egginfo_json
        self.assertIs(dist.flatten_egginfo_json, original)
        utils.stub_dist_flatten_egginfo_json(self, [dist], None)
        self.assertIsNot(dist.flatten_egginfo_json, original)
        self.doCleanups()
        self.assertIs(dist.flatten_egginfo_json, original)

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
            '/service/rpc/lib.js'))
        self.assertTrue(service_records['service/rpc/lib'].startswith(tmpdir))
        self.assertTrue(service_records['service/endpoint'].endswith(
            '/service/endpoint.js'))
        self.assertTrue(service_records['service/endpoint'].startswith(tmpdir))

        # Test out the working set
        framework_dist = working_set.find(Requirement.parse('framework'))
        self.assertEqual(framework_dist.project_name, 'framework')
        self.assertEqual(framework_dist.location, tmpdir)

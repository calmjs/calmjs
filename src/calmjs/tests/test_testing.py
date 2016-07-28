# -*- coding: utf-8 -*-
import unittest
import tempfile

from pkg_resources import WorkingSet
from pkg_resources import Requirement

from os.path import exists
from os.path import join

from calmjs.testing import utils
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import mkdtemp_single
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

    def test_mkdtemp_single_clean_ups(self):
        target = mkdtemp_single(self)
        repeated = mkdtemp_single(self)
        self.assertTrue(exists(target))
        self.assertEqual(target, repeated)  # same dir returned.
        self.assertEqual(self.mock_tempfile.count, 1)  # called once.
        self.assertEqual(self._calmjs_testing_tmpdir, target)
        self.doCleanups()
        self.assertFalse(exists(target))
        self.assertFalse(hasattr(self, '_calmjs_testing_tmpdir'))

        # pretend we go into a different scope
        new_target = mkdtemp_single(self)
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

    def test_setup_testing_module_registry(self):
        # Get the registry.
        from calmjs.base import _ModuleRegistry
        self.assertTrue(isinstance(
            _ModuleRegistry._ModuleRegistry__registry_instances, dict))
        original = {}
        original.update(_ModuleRegistry._ModuleRegistry__registry_instances)

        utils.setup_testing_module_registry(self)
        _ModuleRegistry._ModuleRegistry__registry_instances['foo'] = 'bar'

        self.doCleanups()
        self.assertNotIn(
            'foo', _ModuleRegistry._ModuleRegistry__registry_instances)

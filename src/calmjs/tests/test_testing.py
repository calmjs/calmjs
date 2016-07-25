# -*- coding: utf-8 -*-
import unittest
import tempfile

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
        target = make_dummy_dist(
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

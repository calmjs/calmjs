# -*- coding: utf-8 -*-
import unittest

from os.path import exists
from os.path import join

from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import make_dummy_dist


class TestingUtilsTestCase(unittest.TestCase):
    """
    Some basic harness test case.
    """

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

    def test_mkdtemp_clean_ups(self):
        target = mkdtemp(self)
        self.assertTrue(exists(target))
        self.assertEqual(self._calmjs_testing_tmpdir, target)
        self.doCleanups()
        self.assertFalse(exists(target))
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

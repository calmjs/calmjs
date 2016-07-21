# -*- coding: utf-8 -*-
import unittest

from os.path import exists
from calmjs.testing.utils import mkdtemp


class TestingTestCase(unittest.TestCase):
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
        self.doCleanups()
        self.assertFalse(exists(target))

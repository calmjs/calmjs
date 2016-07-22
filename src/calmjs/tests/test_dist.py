# -*- coding: utf-8 -*-
import unittest
from distutils.errors import DistutilsSetupError

from setuptools.command.egg_info import egg_info
from setuptools.dist import Distribution

from calmjs import dist


class Mock_egg_info(egg_info):

    def initialize_options(self):
        egg_info.initialize_options(self)
        self.called = {}

    def write_or_delete_file(self, what, filename, data, force=True):
        """
        Stub out the actual called function
        """

        self.called[filename] = data


class DistTestCase(unittest.TestCase):
    """
    calmjs.dist module test case.
    """

    def setUp(self):
        self.dist = Distribution()
        self.optname = 'package_json'

    def test_validate_package_json_good(self):
        # don't need to validate against None as "the validation
        # function will only be called if the setup() call sets it to a"
        # non-None value", as per setuptools documentation.

        self.assertTrue(dist.validate_package_json(
            self.dist, self.optname, {}))

    def test_validate_package_json_bad(self):
        with self.assertRaises(DistutilsSetupError) as e:
            dist.validate_package_json(
                self.dist, self.optname, "{},")

        self.assertEqual(
            str(e.exception),
            "'package_json' JSON decoding error: "
            "Extra data: line 1 column 3 - line 1 column 4 (char 2 - 3)"
        )

    def test_write_package_json(self):
        self.dist.package_json = '{}'
        ei = Mock_egg_info(self.dist)
        ei.initialize_options()
        dist.write_package_json(ei, 'package.json', 'package.json')
        self.assertEqual(ei.called['package.json'], '{}')

    def test_write_package_json_dict(self):
        self.dist.package_json = {}
        ei = Mock_egg_info(self.dist)
        ei.initialize_options()
        dist.write_package_json(ei, 'package.json', 'package.json')
        self.assertEqual(ei.called['package.json'], '{}')

    def test_write_package_json_delete(self):
        self.dist.package_json = None  # this triggers the delete
        ei = Mock_egg_info(self.dist)
        ei.initialize_options()
        dist.write_package_json(ei, 'package.json', 'package.json')
        # However since the top level method was stubbed out, just check
        # that it's been called...
        self.assertEqual(ei.called['package.json'], None)

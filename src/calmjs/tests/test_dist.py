# -*- coding: utf-8 -*-
import unittest
from distutils.errors import DistutilsSetupError
import json

from setuptools.dist import Distribution

import pkg_resources

from calmjs import dist as calmjs_dist
from calmjs.testing.mocks import Mock_egg_info
from calmjs.testing.mocks import MockProvider


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

        self.assertTrue(calmjs_dist.validate_package_json(
            self.dist, self.optname, {}))

    def test_validate_package_json_bad(self):
        with self.assertRaises(DistutilsSetupError) as e:
            calmjs_dist.validate_package_json(
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
        calmjs_dist.write_package_json(ei, 'package.json', 'package.json')
        self.assertEqual(ei.called['package.json'], '{}')

    def test_write_package_json_dict(self):
        self.dist.package_json = {}
        ei = Mock_egg_info(self.dist)
        ei.initialize_options()
        calmjs_dist.write_package_json(ei, 'package.json', 'package.json')
        self.assertEqual(ei.called['package.json'], '{}')

    def test_write_package_json_delete(self):
        self.dist.package_json = None  # this triggers the delete
        ei = Mock_egg_info(self.dist)
        ei.initialize_options()
        calmjs_dist.write_package_json(ei, 'package.json', 'package.json')
        # However since the top level method was stubbed out, just check
        # that it's been called...
        self.assertEqual(ei.called['package.json'], None)

    def test_get_pkg_dist(self):
        # Only really testing that this returns an actual distribution
        result = calmjs_dist.get_pkg_dist('setuptools')
        # it's the Distribution class from pkg_resources...
        self.assertTrue(isinstance(result, pkg_resources.Distribution))
        self.assertEqual(result.project_name, 'setuptools')

    def test_get_pkg_json_integrated_live(self):
        # Try reading a fake package.json from setuptools package
        # directly and see that it will just return nothing while not
        # exploding.
        self.assertIsNone(calmjs_dist.read_package_json(
            'setuptools', filename='_not_package.json'))

    def test_get_dist_package_json(self):
        package_json = {"dependencies": {"left-pad": "~1.1.1"}}

        # We will mock up a Distribution object with some fake metadata.
        mock_provider = MockProvider({
            'package.json': json.dumps(package_json),
        })

        mock_dist = pkg_resources.Distribution(
            metadata=mock_provider, project_name='dummydist', version='0.0.0')

        results = calmjs_dist.get_dist_package_json(mock_dist)

        self.assertEqual(results, package_json)

    def test_get_dist_package_decoding_error(self):
        # trailing comma
        package_json = '{"dependencies": {"left-pad": "~1.1.1"},}'
        # bad data could be created by a competiting package.
        mock_provider = MockProvider({
            'package.json': package_json,
        })
        mock_dist = pkg_resources.Distribution(
            metadata=mock_provider, project_name='dummydist', version='0.0.0')

        results = calmjs_dist.get_dist_package_json(mock_dist)

        # Should still not fail.
        self.assertIsNone(results)

    def test_get_dist_package_read_error(self):
        mock_provider = MockProvider({
            'package.json': None,  # None will emulate IO error.
        })
        mock_dist = pkg_resources.Distribution(
            metadata=mock_provider, project_name='dummydist', version='0.0.0')
        results = calmjs_dist.get_dist_package_json(mock_dist)
        # Should still not fail.
        self.assertIsNone(results)

# -*- coding: utf-8 -*-
import unittest
from distutils.errors import DistutilsSetupError
import json

from setuptools.dist import Distribution

import pkg_resources

from calmjs import dist as calmjs_dist
from calmjs.testing.mocks import Mock_egg_info
from calmjs.testing.mocks import MockProvider
from calmjs.testing.utils import make_dummy_dist


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

    def test_get_dist_package_fs(self):
        """
        Use the make_dummy_dist testing util to generate a working
        distribution based on upstream library.
        """

        package_json = {"dependencies": {"left-pad": "~1.1.1"}}
        mock_dist = make_dummy_dist(
            self, (
                ('package.json', json.dumps(package_json)),
            ), pkgname='dummydist'
        )
        results = calmjs_dist.get_dist_package_json(mock_dist)
        self.assertEqual(results['dependencies']['left-pad'], '~1.1.1')

    def tests_flatten_package_json_deps(self):
        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
            ])),
        ), 'security', '9999')

        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'security',
            ])),
            ('package.json', json.dumps({
                'name': 'framework',
                'description': 'some framework',
                'dependencies': {
                    'left-pad': '~1.1.1',
                },
                'devDependencies': {
                    'sinon': '~1.15.0',
                },
            })),
        ), 'framework', '2.4')

        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'framework>=2.1',
            ])),
            ('package.json', json.dumps({
                'dependencies': {
                    'jquery': '~2.0.0',
                    'underscore': '~1.7.0',
                },
            })),
        ), 'widget', '1.1')

        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'framework>=2.2',
                'widget>=1.0',
            ])),
            ('package.json', json.dumps({
                'dependencies': {
                    'backbone': '~1.3.0',
                    'jquery-ui': '~1.12.0',
                },
            })),
        ), 'forms', '1.6')

        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'framework>=2.1',
            ])),
            ('package.json', json.dumps({
                'dependencies': {
                    'underscore': '~1.8.0',
                },
                'devDependencies': {
                    'sinon': '~1.17.0',
                },
            })),
        ), 'service', '1.1')

        site = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'framework>=2.1',
                'widget>=1.1',
                'forms>=1.6',
                'service>=1.1',
            ])),
            ('package.json', json.dumps({
                'name': 'site',
                'dependencies': {
                    'underscore': '~1.8.0',
                    'jquery': '~1.9.0',
                },
            })),
        ), 'site', '2.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])
        result = calmjs_dist.flatten_dist_package_json(site, working_set)
        self.assertEqual(result, {
            'name': 'site',
            'dependencies': {
                'left-pad': '~1.1.1',
                'jquery': '~1.9.0',
                'backbone': '~1.3.0',
                'jquery-ui': '~1.12.0',
                'underscore': '~1.8.0',
            },
            'devDependencies': {
                'sinon': '~1.17.0',
            },
        })

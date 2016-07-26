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

    def test_get_dist_package_json_alternative_name_args(self):
        package_json = {"dependencies": {"left-pad": "~1.1.1"}}

        # We will mock up a Distribution object with some fake metadata.
        mock_provider = MockProvider({
            'bower.json': json.dumps(package_json),
        })

        mock_dist = pkg_resources.Distribution(
            metadata=mock_provider, project_name='dummydist', version='0.0.0')

        results = calmjs_dist.get_dist_package_json(
            mock_dist, filename='bower.json')

        self.assertEqual(results, package_json)

        working_set = pkg_resources.WorkingSet()
        working_set.add(mock_dist)

        self.assertEqual(package_json, calmjs_dist.read_package_json(
            'dummydist', filename='bower.json', working_set=working_set))

        # Finally do the flattening
        flattened_json = {
            "dependencies": {"left-pad": "~1.1.1"}, "devDependencies": {}}
        self.assertEqual(flattened_json, calmjs_dist.flatten_dist_package_json(
            mock_dist, filename='bower.json', working_set=working_set))
        self.assertEqual(flattened_json, calmjs_dist.flatten_package_json(
            'dummydist', filename='bower.json', working_set=working_set))

    def tests_flatten_package_json_deps(self):
        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
            ])),
            ('package.json', 'This is very NOT a package.json.'),
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

        answer = {
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
        }

        # WorkingSet is a frozen representation of the versions and
        # locations of all available package presented through sys.path
        # by default.  Here we just emulate it using our temporary path
        # created by our mock package definitions above.

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        # Ensure that this works with a raw requirement object
        result = calmjs_dist.flatten_dist_package_json(
            site, working_set=working_set)
        self.assertEqual(result, answer)

        # Also a raw requirement (package) string on the other function.
        result = calmjs_dist.flatten_package_json(
            'site', working_set=working_set)
        self.assertEqual(result, answer)

    def tests_flatten_package_json_multi_version(self):
        """
        Need to ensure the *correct* version is picked.
        """

        uilib_1_1 = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.0.0'},
            })),
        ), 'uilib', '1.1.0')

        uilib_1_4 = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.4.0'},
            })),
        ), 'uilib', '1.4.0')

        uilib_1_9 = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.9.0'},
            })),
        ), 'uilib', '1.9.0')

        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'uilib>=1.0',
            ])),
        ), 'app', '2.0')

        # Instead of passing in the tmpdir like the previous test, this
        # working set will be manually created as the situation here
        # should not happen normally - a raw (dist|site)-packages dir
        # with multiple versions of egg-info available for a single
        # importable path - a situation that results in the uilib's
        # actual version being ambiguous.  Anyway, each of these
        # "versions" should be in their own .egg directory with an
        # "EGG-INFO" subdir underneath, with the top level egg path
        # being added to sys.path either through a site.py or some kind
        # of generated program entry point that does that.  For all
        # intents and purposes if the manual Requirements are added to
        # the WorkingSet like so, the expected values presented in the
        # system can be created to behave as if they really exist.

        working_set = pkg_resources.WorkingSet()
        working_set.add(uilib_1_9, self._calmjs_testing_tmpdir)
        working_set.add(app, self._calmjs_testing_tmpdir)

        answer = {
            'dependencies': {
                'jquery': '~1.9.0',
            },
            'devDependencies': {},
        }
        result = calmjs_dist.flatten_package_json(
            'app', working_set=working_set)
        self.assertEqual(result, answer)

        # Now emulate an older version, with a different working set.

        working_set = pkg_resources.WorkingSet()
        working_set.add(uilib_1_4, self._calmjs_testing_tmpdir)
        # this shouldn't override the previous.
        working_set.add(uilib_1_1, self._calmjs_testing_tmpdir)
        working_set.add(app, self._calmjs_testing_tmpdir)

        answer = {
            'dependencies': {
                'jquery': '~1.4.0',
            },
            'devDependencies': {},
        }
        result = calmjs_dist.flatten_package_json(
            'app', working_set=working_set)
        self.assertEqual(result, answer)

    def tests_flatten_package_json_missing_complete(self):
        """
        A completely missing egg should not just blow up.
        """

        working_set = pkg_resources.WorkingSet()
        self.assertEqual(
            {'dependencies': {}, 'devDependencies': {}},
            calmjs_dist.flatten_package_json(
                'nosuchpkg', working_set=working_set))

    def tests_flatten_package_json_missing_deps(self):
        """
        Missing depedencies should not cause a hard failure.
        """

        make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'uilib>=1.0',
            ])),
        ), 'app', '2.0')

        working_set = pkg_resources.WorkingSet([self._calmjs_testing_tmpdir])

        # Python dependency acquisition failures should fail hard.
        with self.assertRaises(pkg_resources.DistributionNotFound):
            calmjs_dist.flatten_package_json('app', working_set=working_set)

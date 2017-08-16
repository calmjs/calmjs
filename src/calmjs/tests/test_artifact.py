# -*- coding: utf-8 -*-
import unittest
from os.path import join
from os.path import normcase
from types import ModuleType

from pkg_resources import WorkingSet

from calmjs import dist
from calmjs.registry import get
from calmjs.artifact import ArtifactRegistry

from calmjs.testing import utils


class IntegrationTestCase(unittest.TestCase):

    def test_integrated_get(self):
        # test that the default registry is registered.
        self.assertTrue(isinstance(get('calmjs.artifacts'), ArtifactRegistry))


class ArtifactRegistryTestCase(unittest.TestCase):
    """
    Standard test cases.
    """

    def assertPathsEqual(self, first, second):
        def norm(items):
            return [normcase(i) for i in items]
        self.assertEqual(norm(first), norm(second))

    def test_verify(self):
        def good_builder(package_names, export_target):
            "An expected argument signature"

        def bad_builder(package_names):
            "An unexpected argument signature"

        self.assertTrue(verify_builder(good_builder))
        self.assertFalse(verify_builder(bad_builder))

    def test_basic(self):
        working_dir = utils.mkdtemp(self)

        utils.make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
            ])),
            ('entry_points.txt', '\n'.join([
                '[calmjs.artifacts]',
                'full.js = calmjs_testbuild:full',
                'base.lib.js = calmjs_testbuild:lib',
            ])),
        ), 'base', '1.0', working_dir=working_dir)

        utils.make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'base',
            ])),
            ('entry_points.txt', '\n'.join([
                '[calmjs.artifacts]',
                'full.js = calmjs_testbuild:full',
                'lib1.lib.js = calmjs_testbuild:lib',
            ])),
        ), 'lib1', '1.0', working_dir=working_dir)

        utils.make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'base',
            ])),
            ('entry_points.txt', '\n'.join([
                '[calmjs.artifacts]',
                'full.js = calmjs_testbuild:full',
                'lib2.lib.js = calmjs_testbuild_extended:lib',
            ])),
        ), 'lib2', '1.0', working_dir=working_dir)

        utils.make_dummy_dist(self, (
            ('requires.txt', '\n'.join([
                'lib1',
                'lib2',
            ])),
            ('entry_points.txt', '\n'.join([
                '[calmjs.artifacts]',
                'full.js = calmjs_testbuild:full',
                # this one doesn't provided a standalone library
            ])),
        ), 'app1', '1.0', working_dir=working_dir)

        mock_ws = WorkingSet([working_dir])

        # stub the default working set in calmjs.dist for the resolver
        # to work.
        utils.stub_item_attr_value(self, dist, 'default_working_set', mock_ws)
        # still specify the working set.
        registry = ArtifactRegistry('calmjs.artifacts', _working_set=mock_ws)

        self.assertNotEqual(len(list(registry.iter_records())), 0)

        self.assertEqual(
            normcase(join(
                working_dir, 'lib1-1.0.egg-info', 'calmjs_artifacts',
                'lib1.lib.js'
            )),
            normcase(registry.get_artifact_filename('lib1', 'lib1.lib.js')),
        )

        self.assertEqual([], list(registry.resolve_artifacts_by_builder_compat(
            ['no_such_package'], 'full')))
        self.assertEqual([], list(registry.resolve_artifacts_by_builder_compat(
            ['lib1'], 'no_such_rule')))

        self.assertPathsEqual([
            join(working_dir, 'lib1-1.0.egg-info', 'calmjs_artifacts',
                 'full.js'),
        ], list(registry.resolve_artifacts_by_builder_compat(
            ['lib1'], 'full')))

        self.assertPathsEqual([
            join(working_dir, 'base-1.0.egg-info', 'calmjs_artifacts',
                 'base.lib.js'),
            join(working_dir, 'lib1-1.0.egg-info', 'calmjs_artifacts',
                 'lib1.lib.js'),
        ], list(registry.resolve_artifacts_by_builder_compat(
            ['lib1'], 'lib', dependencies=True)))

        self.assertPathsEqual([
            join(working_dir, 'base-1.0.egg-info', 'calmjs_artifacts',
                 'base.lib.js'),
            join(working_dir, 'lib2-1.0.egg-info', 'calmjs_artifacts',
                 'lib2.lib.js'),
            join(working_dir, 'lib1-1.0.egg-info', 'calmjs_artifacts',
                 'lib1.lib.js'),
        ], list(registry.resolve_artifacts_by_builder_compat(
            ['lib2', 'lib1'], 'lib', dependencies=True)))

        self.assertPathsEqual([
            join(working_dir, 'base-1.0.egg-info', 'calmjs_artifacts',
                 'base.lib.js'),
            join(working_dir, 'lib1-1.0.egg-info', 'calmjs_artifacts',
                 'lib1.lib.js'),
            join(working_dir, 'lib2-1.0.egg-info', 'calmjs_artifacts',
                 'lib2.lib.js'),
        ], list(registry.resolve_artifacts_by_builder_compat(
            ['app1'], 'lib', dependencies=True)))

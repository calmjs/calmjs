# -*- coding: utf-8 -*-
import logging
import unittest
import sys
from distutils.dist import Distribution
from distutils.errors import DistutilsModuleError

from calmjs.command import distutils_log_handler
from calmjs.command import BuildArtifactCommand

from calmjs.testing.utils import stub_stdouts


# the actual command class kind of requires integration test for most
# effectiveness, since it's a relatively thin shim on top of the
# underlying driver class.


class DistLoggerTestCase(unittest.TestCase):
    """
    Test for the adapter from standard logging to the distutils version.
    """

    def setUp(self):
        stub_stdouts(self)

    def tearDown(self):
        distutils_log_handler.log.set_threshold(distutils_log_handler.log.WARN)

    def test_logging_bad(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(0)
        logger.addHandler(distutils_log_handler)
        logger.log(9001, 'Over 9000 will definitely not work')
        self.assertEqual(sys.stdout.getvalue(), '')
        self.assertTrue(sys.stderr.getvalue().startswith(
            'Failed to convert <LogRecord: calmjs.testing.dummy, 9001'))

    def test_logging_all(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(2)
        logger.addHandler(distutils_log_handler)
        logger.critical('Critical')
        logger.error('Error')
        logger.warning('Warning')
        logger.info('Information')
        logger.debug('Debug')
        self.assertEqual(sys.stderr.getvalue(), 'Critical\nError\nWarning\n')
        self.assertEqual(sys.stdout.getvalue(), 'Information\nDebug\n')

    def test_logging_info_only(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(1)
        logger.addHandler(distutils_log_handler)
        logger.info('Information')
        logger.debug('Debug')
        self.assertEqual(sys.stdout.getvalue(), 'Information\n')

    def test_logging_errors_only(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(0)
        logger.addHandler(distutils_log_handler)
        logger.info('Information')
        logger.debug('Debug')
        logger.warning('Warning')
        self.assertEqual(sys.stdout.getvalue(), '')
        self.assertEqual(sys.stderr.getvalue(), 'Warning\n')


class BuildArtifactCommandTestcase(unittest.TestCase):
    """
    Just a basic test with stubbed contents.
    """

    def setUp(self):
        # complete integration test will be difficult to achieve, so
        # this series of stubs and direct invocation will be done
        # instead.
        built_names = []

        class FakeBuilder(object):
            registry_name = 'demo.artifacts'

            def __call__(self, package_names):
                built_names.extend(package_names)
                return 'fail.package' not in package_names

        self.builder = FakeBuilder()
        self.built_names = built_names

    def test_build_calmjs_artifacts_misconfigured(self):
        dist = Distribution(attrs={
            'name': 'some.package',
        })
        cmd = BuildArtifactCommand(dist=dist)
        with self.assertRaises(DistutilsModuleError) as e:
            cmd.run()

        self.assertIn('artifact_builder is not callable for', str(e.exception))

    def test_build_calmjs_artifacts_dry_run(self):
        dist = Distribution(attrs={
            'name': 'some.package',
            'dry_run': True,
        })
        cmd = BuildArtifactCommand(dist=dist)
        # usually this is defined in the subclass as a class attribute
        cmd.artifact_builder = self.builder
        cmd.run()
        self.assertEqual([], self.built_names)

    def test_build_calmjs_artifacts_success(self):
        dist = Distribution(attrs={
            'name': 'some.package',
        })
        cmd = BuildArtifactCommand(dist=dist)
        cmd.artifact_builder = self.builder
        cmd.run()
        self.assertEqual(['some.package'], self.built_names)

    def test_build_calmjs_artifacts_failure(self):
        dist = Distribution(attrs={
            'name': 'fail.package',
        })
        cmd = BuildArtifactCommand(dist=dist)
        cmd.artifact_builder = self.builder
        with self.assertRaises(DistutilsModuleError) as e:
            cmd.run()
        # gets appended as an attempt
        self.assertEqual(['fail.package'], self.built_names)
        self.assertIn(
            "some entries in registry 'demo.artifacts' defined for package "
            "'fail.package' failed to generate an artifact", str(e.exception),
        )

# -*- coding: utf-8 -*-
import logging
import unittest
import sys
from distutils.dist import Distribution

from calmjs import command
from calmjs.command import distutils_log_handler
from calmjs.command import BuildArtifactCommand

from calmjs.testing.utils import stub_stdouts
from calmjs.testing.utils import stub_item_attr_value


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
            def build_artifacts(self, name):
                built_names.append(name)

        self.built_names = built_names
        stub_item_attr_value(self, command, 'get', {
            'calmjs.artifacts': FakeBuilder(),
        }.get)

    def test_build_calmjs_artifacts_dry_run(self):
        dist = Distribution(attrs={
            'name': 'some.package',
            'dry_run': True,
        })
        cmd = BuildArtifactCommand(dist=dist)
        cmd.run()
        self.assertEqual([], self.built_names)

    def test_build_calmjs_artifacts_basic(self):
        dist = Distribution(attrs={
            'name': 'some.package',
        })
        cmd = BuildArtifactCommand(dist=dist)
        cmd.run()
        self.assertEqual(['some.package'], self.built_names)

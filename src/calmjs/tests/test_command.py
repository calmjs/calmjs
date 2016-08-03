# -*- coding: utf-8 -*-
import logging
import unittest
import sys

from calmjs.command import distutils_log_handler

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

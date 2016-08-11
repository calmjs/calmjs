import unittest
import doctest
from os.path import dirname


def make_suite():  # pragma: no cover
    import calmjs.registry
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(
        'calmjs.tests', pattern='test_*.py',
        top_level_dir=dirname(__file__),
    )
    # setting up the finder is a bit annoying for just a one-off.
    test_suite.addTest(doctest.DocTestSuite(calmjs.registry))
    return test_suite

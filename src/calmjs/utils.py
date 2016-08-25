# -*- coding: utf-8 -*-
"""
Assortment of utility functions.
"""

import os
import logging
from contextlib import contextmanager
from os.path import curdir
from os.path import defpath
from os.path import normcase
from os.path import pathsep
import sys


def enable_pretty_logging(logger='calmjs', level=logging.DEBUG, stream=None):
    """
    Shorthand to enable pretty logging
    """

    def cleanup():
        logger.removeHandler(handler)
        logger.level = old_level

    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)

    old_level = logger.level
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(level)
    return cleanup


@contextmanager
def pretty_logging(logger='calmjs', level=logging.DEBUG, stream=None):
    try:
        cleanup = enable_pretty_logging(logger, level, stream)
        yield
    finally:
        cleanup()


def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """
    Given cmd, check where it is on PATH.

    Loosely based on the version in python 3.3.
    """

    if path is None:
        path = os.environ.get('PATH', defpath)
    if not path:
        return None

    paths = path.split(pathsep)

    if sys.platform == 'win32':
        # oh boy
        if curdir not in paths:
            paths = [curdir] + paths

        # also need to check the fileexts...
        pathext = os.environ.get('PATHEXT', '').split(pathsep)

        if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # sanity
        files = [cmd]

    seen = set()
    for p in paths:
        normpath = normcase(p)
        if normpath in seen:
            continue
        seen.add(normpath)
        for f in files:
            fn = os.path.join(p, f)
            if os.path.isfile(fn) and os.access(fn, mode):
                return fn

    return None

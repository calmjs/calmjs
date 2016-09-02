# -*- coding: utf-8 -*-
"""
Assortment of utility functions.
"""

from __future__ import absolute_import
from __future__ import unicode_literals

import logging
import os
import sys
from contextlib import contextmanager
from locale import getpreferredencoding
from os import strerror
from os.path import curdir
from os.path import defpath
from os.path import normcase
from os.path import pathsep
from pdb import post_mortem
from subprocess import Popen
from subprocess import PIPE

locale = getpreferredencoding()


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
        yield stream
    finally:
        cleanup()


def fork_exec(args, stdin='', **kwargs):
    """
    Do a fork-exec through the subprocess.Popen abstraction in a way
    that takes a stadin and return stdout.
    """

    as_bytes = isinstance(stdin, bytes)
    source = stdin if as_bytes else stdin.encode(locale)
    p = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
    stdout, stderr = p.communicate(source)
    if as_bytes:
        return stdout, stderr
    return (stdout.decode(locale), stderr.decode(locale))


def raise_os_error(_errno):
    """
    Helper for raising the correct exception under Python 3 while still
    being able to raise the same common exception class in Python 2.7.
    """

    raise OSError(_errno, strerror(_errno))


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


def pdb_post_mortem(*a, **kw):
    post_mortem(*a, **kw)

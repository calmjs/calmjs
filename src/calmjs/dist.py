# -*- coding: utf-8 -*-
"""
Module for the integration with distutils/setuptools.

Provides functions and classes that enable the management of npm
dependencies for JavaScript sources that lives in Python packages.
"""

from distutils.core import Command
from distutils.errors import DistutilsSetupError
from distutils import log

import json

from calmjs.npm import verify_package_json


def validate_package_json(dist, attr, value):
    """
    Check for package_json validity.
    """

    try:
        verify_package_json(value)
    except ValueError as e:
        raise DistutilsSetupError("%r %s" % (attr, e))

    return True


def write_package_json(cmd, basename, filename):
    """
    Write the defined package_json into the package's egg-info directory
    as ``package.json``.
    """

    argname = 'package_json'

    value = getattr(cmd.distribution, argname, None)

    if isinstance(value, dict):
        value = json.dumps(value, indent=4)

    cmd.write_or_delete_file(argname, filename, value, force=True)

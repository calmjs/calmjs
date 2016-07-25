# -*- coding: utf-8 -*-
"""
Module for the integration with distutils/setuptools.

Provides functions and classes that enable the management of npm
dependencies for JavaScript sources that lives in Python packages.
"""

from distutils.core import Command
from distutils.errors import DistutilsSetupError
from distutils import log

import pkg_resources
from pkg_resources import Environment
from pkg_resources import Requirement
from pkg_resources import resource_string
from pkg_resources import resource_stream

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


def get_pkg_dist(pkg_name, env=None, working_set=pkg_resources.working_set):
    """
    Locate a package's distribution by its name.
    """

    if env is None:
        env = Environment()
    req = Requirement.parse(pkg_name)
    return env.best_match(req, working_set)


def get_dist_package_json(dist, filename='package.json'):
    """
    Safely get a package_json from a distribution.
    """

    # Then use the package's distribution to acquire the file.
    if not dist.has_metadata(filename):
        log.debug("No '%s' found for '%s'.", filename, dist)
        return

    try:
        result = dist.get_metadata(filename)
    except IOError:
        log.error("Failed to read '%s' for '%s'.", filename, dist)
        return

    try:
        obj = json.loads(result)
    except (TypeError, ValueError) as e:
        log.error(
            "The '%s' found in '%s' is not a valid json.", filename, dist)
        return

    return obj


def read_package_json(pkg_name, filename='package.json'):
    """
    Read the package.json of a package identified by `pkg_name` that's
    already installed within the current Python environment.
    """

    dist = get_pkg_dist(pkg_name)
    return get_dist_package_json(dist, filename)

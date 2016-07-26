# -*- coding: utf-8 -*-
"""
Module for the integration with distutils/setuptools.

Provides functions and classes that enable the management of npm
dependencies for JavaScript sources that lives in Python packages.
"""

from distutils.errors import DistutilsSetupError
from distutils import log

from pkg_resources import Requirement
from pkg_resources import working_set as default_working_set

import json

from calmjs.npm import verify_package_json
from calmjs.npm import PACKAGE_JSON


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


def get_pkg_dist(pkg_name, working_set=default_working_set):
    """
    Locate a package's distribution by its name.
    """

    req = Requirement.parse(pkg_name)
    return working_set.find(req)


def get_dist_package_json(dist, filename=PACKAGE_JSON):
    """
    Safely get a package_json from a distribution.
    """

    # Then use the package's distribution to acquire the file.
    if not dist.has_metadata(filename):
        log.debug("No '%s' for '%s'.", filename, dist)
        return

    try:
        result = dist.get_metadata(filename)
    except IOError:
        log.error("Failed to read '%s' for '%s'.", filename, dist)
        return

    try:
        obj = json.loads(result)
    except (TypeError, ValueError):
        log.error(
            "The '%s' found in '%s' is not a valid json.", filename, dist)
        return

    log.debug("Found '%s' for '%s'.", filename, dist)
    return obj


def read_package_json(
        pkg_name, filename=PACKAGE_JSON, working_set=default_working_set):
    """
    Read the package.json of a package identified by `pkg_name` that's
    already installed within the current Python environment.
    """

    dist = get_pkg_dist(pkg_name, working_set=working_set)
    return get_dist_package_json(dist, filename)


def flatten_dist_package_json(
        source_dist, filename=PACKAGE_JSON, working_set=default_working_set):
    """
    Resolve a distribution's (dev)dependencies through the working set
    and generate a flattened version package.json, returned as a dict,
    from the resolved distributions.

    Default working set is the one from pkg_resources.

    The generated package.json dict is done by grabbing all package.json
    metadata from all parent Python packages, starting from the highest
    level and down to the lowest.  The current distribution's
    dependencies will be layered on top along with its other package
    information.  This has the effect of child packages overriding
    node/npm dependencies which is by the design of this function.  If
    nested dependencies are desired, just rely on npm only for all
    dependency management.

    Flat is better than nested.
    """

    dependencies = {}
    devDependencies = {}

    # ensure that we have at least a dummy value
    if source_dist:
        requires = source_dist.requires()
        root = get_dist_package_json(source_dist, filename) or {}
    else:
        requires = []
        root = {}

    # Go from the earliest package down to the latest one, as we will
    # flatten children's d(evD)ependencies on top of parent's.
    for dist in reversed(working_set.resolve(requires)):
        obj = get_dist_package_json(dist, filename)
        if not obj:
            continue

        dependencies.update(obj.get('dependencies', {}))
        devDependencies.update(obj.get('devDependencies', {}))

    # Layer on top
    dependencies.update(root.get('dependencies', {}))
    devDependencies.update(root.get('devDependencies', {}))

    root['dependencies'] = dependencies
    root['devDependencies'] = devDependencies

    return root


def flatten_package_json(
        pkg_name, filename=PACKAGE_JSON, working_set=default_working_set):
    """
    Generate a flattened package.json of a package `pkg_name` that's
    already installed within the current Python environment (defaults
    to the current global working_set which should have been set up
    correctly by pkg_resources).
    """

    dist = get_pkg_dist(pkg_name, working_set=working_set)
    return flatten_dist_package_json(dist, filename, working_set)

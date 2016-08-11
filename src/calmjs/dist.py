# -*- coding: utf-8 -*-
"""
Module for the integration with distutils/setuptools.

Provides functions and classes that enable the management of npm
dependencies for JavaScript sources that lives in Python packages.
"""

from logging import getLogger

from distutils.errors import DistutilsSetupError

from pkg_resources import Requirement
from pkg_resources import working_set as default_working_set

import json

logger = getLogger(__name__)

# default package definition filename.
DEFAULT_JSON = 'default.json'


def is_json_compat(value):
    """
    Check that the value is either a JSON decodable string or a dict
    that can be encoded into a JSON.

    Raises ValueError when validation fails.
    """

    try:
        value = json.loads(value)
    except ValueError as e:
        raise ValueError('JSON decoding error: ' + str(e))
    except TypeError:
        # Check that the value can be serialized back into json.
        try:
            json.dumps(value)
        except TypeError as e:
            raise ValueError(
                'must be a JSON serializable object: ' + str(e))

    if not isinstance(value, dict):
        raise ValueError(
            'must be specified as a JSON serializable dict or a '
            'JSON deserializable string'
        )

    return True


def validate_json_field(dist, attr, value):
    """
    Check for json validity.
    """

    try:
        is_json_compat(value)
    except ValueError as e:
        raise DistutilsSetupError("%r %s" % (attr, e))

    return True


def write_json_file(argname, cmd, basename, filename):
    """
    Write JSON captured from the defined argname into the package's
    egg-info directory using the specified filename.
    """

    value = getattr(cmd.distribution, argname, None)

    if isinstance(value, dict):
        value = json.dumps(
            value, indent=4, sort_keys=True, separators=(',', ': '))

    cmd.write_or_delete_file(argname, filename, value, force=True)


def get_pkg_dist(pkg_name, working_set=default_working_set):
    """
    Locate a package's distribution by its name.
    """

    req = Requirement.parse(pkg_name)
    return working_set.find(req)


def get_dist_package_json(dist, filename=DEFAULT_JSON):
    """
    Safely get a package_json from a distribution.
    """

    # Then use the package's distribution to acquire the file.
    if not dist.has_metadata(filename):
        logger.debug("no '%s' for '%s'", filename, dist)
        return

    try:
        result = dist.get_metadata(filename)
    except IOError:
        logger.error("I/O error on reading of '%s' for '%s'.", filename, dist)
        return

    try:
        obj = json.loads(result)
    except (TypeError, ValueError):
        logger.error(
            "the '%s' found in '%s' is not a valid json.", filename, dist)
        return

    logger.debug("found '%s' for '%s'.", filename, dist)
    return obj


def read_package_json(
        pkg_name, filename=DEFAULT_JSON, working_set=default_working_set):
    """
    Read the package.json of a package identified by `pkg_name` that's
    already installed within the current Python environment.
    """

    dist = get_pkg_dist(pkg_name, working_set=working_set)
    return get_dist_package_json(dist, filename)


def flatten_dist_package_json(
        source_dist, filename=DEFAULT_JSON, working_set=default_working_set):
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

        logger.debug("merging '%s' for required '%s'", filename, dist)
        dependencies.update(obj.get('dependencies', {}))
        devDependencies.update(obj.get('devDependencies', {}))

    if source_dist:
        # Layer on top
        logger.debug("merging '%s' for target '%s'", filename, source_dist)
        dependencies.update(root.get('dependencies', {}))
        devDependencies.update(root.get('devDependencies', {}))

    root['dependencies'] = {
        k: v for k, v in dependencies.items() if v is not None}
    root['devDependencies'] = {
        k: v for k, v in devDependencies.items() if v is not None}

    return root


def flatten_package_json(
        pkg_name, filename=DEFAULT_JSON, working_set=default_working_set):
    """
    Generate a flattened package.json of a package `pkg_name` that's
    already installed within the current Python environment (defaults
    to the current global working_set which should have been set up
    correctly by pkg_resources).
    """

    dist = get_pkg_dist(pkg_name, working_set=working_set)
    return flatten_dist_package_json(dist, filename, working_set)

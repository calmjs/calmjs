# -*- coding: utf-8 -*-
"""
Module for the integration with distutils/setuptools.

Provides functions and classes that enable the management of npm
dependencies for JavaScript sources that lives in Python packages.
"""

from __future__ import absolute_import
import json

from functools import partial
from logging import getLogger

from distutils.command.build import build as BuildCommand
from distutils.errors import DistutilsSetupError

from pkg_resources import Requirement
from pkg_resources import working_set as default_working_set

from calmjs.registry import get
from calmjs.base import BaseModuleRegistry

logger = getLogger(__name__)

# default package definition filename.
JSON_EXTRAS_REGISTRY_KEY = 'calmjs.extras_keys'
CALMJS_MODULE_REGISTRY_FIELD = 'calmjs_module_registry'
CALMJS_MODULE_REGISTRY_TXT = 'calmjs_module_registry.txt'
DEFAULT_JSON = 'default.json'
EXTRAS_CALMJS_FIELD = 'extras_calmjs'
EXTRAS_CALMJS_JSON = 'extras_calmjs.json'
DEP_KEYS = ('dependencies', 'devDependencies')
TEST_REGISTRY_NAME_SUFFIX = '.tests'


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


def validate_line_list(dist, attr, value):
    """
    Validate that the value is compatible
    """

    # does not work as reliably in Python 2.
    if isinstance(value, str):
        value = value.split()
    value = list(value)

    try:
        check = (' '.join(value)).split()
        if check == value:
            return True
    except Exception:
        pass
    raise DistutilsSetupError("%r must be a list of valid identifiers" % attr)


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


def write_line_list(argname, cmd, basename, filename):
    """
    Write out the retrieved value as list of lines.
    """

    values = getattr(cmd.distribution, argname, None)
    if isinstance(values, list):
        values = '\n'.join(values)
    cmd.write_or_delete_file(argname, filename, values, force=True)


def find_pkg_dist(pkg_name, working_set=None):
    """
    Locate a package's distribution by its name.
    """

    working_set = working_set or default_working_set
    req = Requirement.parse(pkg_name)
    return working_set.find(req)


def convert_package_names(package_names):
    """
    Convert package names, which can be a string of a number of package
    names or requirements separated by spaces.
    """

    results = []
    errors = []

    for name in (
            package_names.split()
            if hasattr(package_names, 'split') else package_names):
        try:
            Requirement.parse(name)
        except ValueError:
            errors.append(name)
        else:
            results.append(name)

    return results, errors


def pkg_names_to_dists(pkg_names, working_set=None):
    working_set = working_set or default_working_set
    return [dist for dist in (find_pkg_dist(
        pkg_name, working_set=working_set) for pkg_name in pkg_names) if dist]


def find_packages_requirements_dists(pkg_names, working_set=None):
    """
    Return the entire list of dependency requirements, reversed from the
    bottom.
    """

    working_set = working_set or default_working_set
    requirements = [
        r for r in (Requirement.parse(req) for req in pkg_names)
        if working_set.find(r)
    ]
    return list(reversed(working_set.resolve(requirements)))


def find_packages_parents_requirements_dists(pkg_names, working_set=None):
    """
    Leverages the `find_packages_requirements_dists` but strip out the
    distributions that matches pkg_names.
    """

    dists = []
    # opting for a naive implementation
    targets = set(pkg_names)
    for dist in find_packages_requirements_dists(pkg_names, working_set):
        if dist.project_name in targets:
            continue
        dists.append(dist)
    return dists


def read_dist_egginfo_json(dist, filename=DEFAULT_JSON):
    """
    Safely get a json within an egginfo from a distribution.
    """

    # use the given package's distribution to acquire the json file.
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


def read_egginfo_json(pkg_name, filename=DEFAULT_JSON, working_set=None):
    """
    Read json from egginfo of a package identified by `pkg_name` that's
    already installed within the current Python environment.
    """

    working_set = working_set or default_working_set
    dist = find_pkg_dist(pkg_name, working_set=working_set)
    return read_dist_egginfo_json(dist, filename)


def read_dist_line_list(dist, filename):
    if not dist.has_metadata(filename):
        return []

    try:
        result = dist.get_metadata(filename)
    except IOError:
        # not as critical as egginfo json, as typical usage these can
        # be easily overridden
        logger.warning("I/O error on reading of '%s' for '%s'", filename, dist)
        return []

    return result.split()


def flatten_dist_egginfo_json(
        source_dists, filename=DEFAULT_JSON, dep_keys=DEP_KEYS,
        working_set=None):
    """
    Flatten a distribution's egginfo json, with the depended keys to be
    flattened.

    Originally this was done for this:

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

    working_set = working_set or default_working_set
    obj = {}

    # TODO figure out the best way to explicitly report back to caller
    # how the keys came to be (from which dist).  Perhaps create a
    # detailed function based on this, retain this one to return the
    # distilled results.

    depends = {dep: {} for dep in dep_keys}

    # Go from the earliest package down to the latest one, as we will
    # flatten children's d(evD)ependencies on top of parent's.
    for dist in source_dists:
        obj = read_dist_egginfo_json(dist, filename)
        if not obj:
            continue

        logger.debug("merging '%s' for required '%s'", filename, dist)
        for dep in dep_keys:
            depends[dep].update(obj.get(dep, {}))

    if obj is None:
        # top level object does not have egg-info defined
        return depends

    for dep in dep_keys:
        # filtering out all the nulls.
        obj[dep] = {k: v for k, v in depends[dep].items() if v is not None}

    return obj


def flatten_egginfo_json(
        pkg_names, filename=DEFAULT_JSON, dep_keys=DEP_KEYS, working_set=None):
    """
    A shorthand calling convention where the package name is supplied
    instead of a distribution.

    Originally written for this:

    Generate a flattened package.json with packages `pkg_names` that are
    already installed within the current Python environment (defaults
    to the current global working_set which should have been set up
    correctly by pkg_resources).
    """

    working_set = working_set or default_working_set
    # Ensure only grabbing packages that exists in working_set
    dists = find_packages_requirements_dists(
        pkg_names, working_set=working_set)
    return flatten_dist_egginfo_json(
        dists, filename=filename, dep_keys=dep_keys, working_set=working_set)


def build_helpers_egginfo_json(
        json_field, json_key_registry, json_filename=None):
    """
    Return a tuple of functions that will provide the usage of the
    JSON egginfo based around the provided field.
    """

    json_filename = (
        json_field + '.json' if json_filename is None else json_filename)

    # Default calmjs core implementation specific functions, to be used by
    # integrators intended to use this as a distribution.

    def get_extras_json(pkg_names, working_set=None):
        """
        Only extract the extras_json information for the given packages
        'pkg_names'.
        """

        working_set = working_set or default_working_set
        dep_keys = set(get(json_key_registry).iter_records())
        dists = pkg_names_to_dists(pkg_names, working_set=working_set)
        return flatten_dist_egginfo_json(
            dists, filename=json_filename,
            dep_keys=dep_keys, working_set=working_set
        )

    def _flatten_extras_json(pkg_names, find_dists, working_set):
        # registry key must be explicit here as it was designed for this.
        dep_keys = set(get(json_key_registry).iter_records())
        dists = find_dists(pkg_names, working_set=working_set)
        return flatten_dist_egginfo_json(
            dists, filename=json_filename,
            dep_keys=dep_keys, working_set=working_set
        )

    def flatten_extras_json(pkg_names, working_set=None):
        """
        Traverses through the dependency graph of packages 'pkg_names'
        and flattens all the egg_info json information
        """

        working_set = working_set or default_working_set
        return _flatten_extras_json(
            pkg_names, find_packages_requirements_dists, working_set)

    def flatten_parents_extras_json(pkg_names, working_set=None):
        """
        Traverses through the dependency graph of packages 'pkg_names'
        and flattens all the egg_info json information for parents of
        the specified packages.
        """

        working_set = working_set or default_working_set
        return _flatten_extras_json(
            pkg_names, find_packages_parents_requirements_dists, working_set)

    write_extras_json = partial(write_json_file, json_field)

    return (
        get_extras_json,
        flatten_extras_json,
        flatten_parents_extras_json,
        write_extras_json,
    )


(get_extras_calmjs, flatten_extras_calmjs, flatten_parents_extras_calmjs,
    write_extras_calmjs) = build_helpers_egginfo_json(
        EXTRAS_CALMJS_FIELD, JSON_EXTRAS_REGISTRY_KEY)


def build_helpers_module_registry_dependencies(registry_name='calmjs.module'):
    """
    Return a tuple of funtions that will provide the functions that
    return the relevant sets of module registry records based on the
    dependencies defined for the provided packages.
    """

    def get_module_registry_dependencies(
            pkg_names, registry_name=registry_name, working_set=None):
        """
        Get dependencies for the given package names from module
        registry identified by registry name.

        For the given packages 'pkg_names' and the registry identified
        by 'registry_name', resolve the exported location for just the
        package.
        """

        working_set = working_set or default_working_set
        registry = get(registry_name)
        if not isinstance(registry, BaseModuleRegistry):
            return {}
        result = {}
        for pkg_name in pkg_names:
            result.update(registry.get_records_for_package(pkg_name))
        return result

    def _flatten_module_registry_dependencies(
            pkg_names, registry_name, find_dists, working_set):
        """
        Flatten dependencies for the given package names from module
        registry identified by registry name using the find_dists
        function on the given working_set.

        For the given packages 'pkg_names' and the registry identified
        by 'registry_name', resolve and flatten all the exported
        locations.
        """

        result = {}
        registry = get(registry_name)
        if not isinstance(registry, BaseModuleRegistry):
            return result

        dists = find_dists(pkg_names, working_set=working_set)
        for dist in dists:
            result.update(registry.get_records_for_package(dist.project_name))

        return result

    def flatten_module_registry_dependencies(
            pkg_names, registry_name=registry_name, working_set=None):
        """
        Flatten dependencies for the specified packages from the module
        registry identified by registry name.

        For the given packages 'pkg_names' and the registry identified
        by 'registry_name', resolve and flatten all the exported
        locations.
        """

        working_set = working_set or default_working_set
        return _flatten_module_registry_dependencies(
            pkg_names, registry_name, find_packages_requirements_dists,
            working_set)

    def flatten_parents_module_registry_dependencies(
            pkg_names, registry_name=registry_name, working_set=None):
        """
        Flatten dependencies for the parents of the specified packages
        from the module registry identified by registry name.

        For the given packages 'pkg_names' and the registry identified
        by 'registry_name', resolve and flatten all the exported
        locations.
        """

        working_set = working_set or default_working_set
        return _flatten_module_registry_dependencies(
            pkg_names, registry_name, find_packages_parents_requirements_dists,
            working_set)

    return (
        get_module_registry_dependencies,
        flatten_module_registry_dependencies,
        flatten_parents_module_registry_dependencies,
    )


(get_module_registry_dependencies, flatten_module_registry_dependencies,
    flatten_parents_module_registry_dependencies) = (
        build_helpers_module_registry_dependencies())


def _uniq(items):
    check = set()
    return [i for i in items if not (i in check or check.add(i))]


def build_helpers_module_registry_name(
        registry_field, registry_field_txt=None):

    registry_field_txt = (
        registry_field + '.txt' if registry_field_txt is None else
        registry_field_txt
    )

    def get_module_registry_names(pkg_names, working_set=None):
        """
        Get names of module registries registered for package names.

        For the given packages 'pkg_names', retrieve the list of module
        registries explicitly declared for usage.
        """

        ws = working_set or default_working_set
        result = []
        for dist in pkg_names_to_dists(pkg_names, working_set=ws):
            result.extend(read_dist_line_list(dist, registry_field_txt))
        return _uniq(result)

    def flatten_module_registry_names(pkg_names, working_set=None):
        """
        Flatten all names of module registries registered for package names.

        For the given packages 'pkg_names' and its dependencies, retrieve
        the list of module registries explicitly declared for usage.
        """

        ws = working_set or default_working_set
        result = []
        for dist in find_packages_requirements_dists(
                pkg_names, working_set=ws):
            result.extend(read_dist_line_list(dist, registry_field_txt))
        return _uniq(result)

    write_module_registry_names = partial(write_line_list, registry_field)

    return (
        get_module_registry_names,
        flatten_module_registry_names,
        write_module_registry_names,
    )


(get_module_registry_names, flatten_module_registry_names,
    write_module_registry_names) = build_helpers_module_registry_name(
        CALMJS_MODULE_REGISTRY_FIELD)


# These depend on the artifact registry that is defined in the artifact
# module.

def has_calmjs_artifact_declarations(cmd, registry_name='calmjs.artifacts'):
    """
    For a distutils command to verify that the artifact build step is
    possible.
    """

    return any(get(registry_name).iter_records_for(
        cmd.distribution.get_name()))


def build_calmjs_artifacts(dist, key, value, cmdclass=BuildCommand):
    """
    Trigger the artifact build process through the setuptools.
    """

    if value is not True:
        return

    build_cmd = dist.get_command_obj('build')
    if not isinstance(build_cmd, cmdclass):
        logger.error(
            "'build' command in Distribution is not an instance of "
            "'%s:%s' (got %r instead)",
            cmdclass.__module__, cmdclass.__name__, build_cmd)
        return

    build_cmd.sub_commands.append((key, has_calmjs_artifact_declarations))

# -*- coding: utf-8 -*-
"""
Compatibility layer for the subset of the ``pkg_resources`` API that is
used by this framework.

The ``pkg_resources`` module is deprecated and is no longer guaranteed
to be available on all supported Python environments, so this module
reimplements the required behaviour on top of ``importlib`` and the
``packaging`` library.  The provided interfaces intentionally mirror
their ``pkg_resources`` counterparts, so that the rest of the framework
(and its tests) keep working the same way as they did before.
"""

from __future__ import absolute_import

import email
import importlib
import logging
import os
import re
import sys
from configparser import ConfigParser

from packaging.requirements import Requirement as _PackagingRequirement

logger = logging.getLogger(__name__)

# the metadata directory suffixes recognized on path entries.
META_SUFFIXES = ('.dist-info', '.egg-info')


def safe_name(name):
    """
    Convert an arbitrary string to a standard distribution name.

    Any runs of non-alphanumeric/. characters are replaced with a
    single '-'.
    """

    return re.sub('[^A-Za-z0-9.]+', '-', name)


class ResolutionError(Exception):
    """
    Base class for resolve errors, mostly for the intent of providing
    the requirement that caused the failure.
    """

    def __init__(self, req):
        super(ResolutionError, self).__init__(req)
        self.req = req

    def __str__(self):
        return "Unable to resolve '%s'." % self.req


class DistributionNotFound(ResolutionError):
    """
    A requested distribution could not be found.
    """


class VersionConflict(ResolutionError):
    """
    An already-provided distribution does not meet the requested
    version specification.
    """

    def __init__(self, dist, req):
        super(VersionConflict, self).__init__(req)
        self.dist = dist

    def __str__(self):
        return "Version conflict for '%s' (%s installed)." % (
            self.req, self.dist)


class Requirement(_PackagingRequirement):
    """
    A requirement, as parsed from a string; mirrors the interface of
    ``pkg_resources.Requirement`` as used by this framework.
    """

    @classmethod
    def parse(cls, string):
        return cls(string)

    @property
    def project_name(self):
        return self.name

    @property
    def key(self):
        return self.name.lower()

    def __contains__(self, item):
        version = getattr(item, 'version', None)
        if version is None:
            return not self.specifier
        return self.specifier.contains(version, prereleases=True)


class EntryPoint(object):
    """
    An entry point as declared by a distribution; mirrors the interface
    of ``pkg_resources.EntryPoint`` as used by this framework.
    """

    pattern = re.compile(
        r'\s*(?P<name>.+?)\s*=\s*(?P<module>[\w.]+)\s*'
        r'(:\s*(?P<attr>[\w.]+))?\s*(?P<extras>\[.*\])?\s*$'
    )

    def __init__(self, name, module_name, attrs=(), extras=(), group=None):
        self.name = name
        self.module_name = module_name
        self.attrs = tuple(attrs)
        self.extras = tuple(extras)
        self.group = group
        self.dist = None

    @classmethod
    def parse(cls, src, group=None):
        match = cls.pattern.match(src)
        if not match:
            raise ValueError(
                "EntryPoint must be in 'name=module:attrs [extras]' format")
        res = match.groupdict()
        extras = cls._parse_extras(res['extras'])
        attrs = res['attr'].split('.') if res['attr'] else ()
        return cls(res['name'], res['module'], attrs, extras, group)

    @classmethod
    def _parse_extras(cls, extras_spec):
        if not extras_spec:
            return ()
        return tuple(sorted(Requirement.parse('x' + extras_spec).extras))

    def load(self, require=True):
        module = importlib.import_module(self.module_name)
        target = module
        for attr in self.attrs:
            try:
                target = getattr(target, attr)
            except AttributeError:
                raise ImportError(
                    "No '%s' attribute found in '%s' for entry point '%s'" % (
                        attr, self.module_name, self))
        return target

    def resolve(self):
        return self.load(require=False)

    def __str__(self):
        result = '%s = %s' % (self.name, self.module_name)
        if self.attrs:
            result += ':' + '.'.join(self.attrs)
        if self.extras:
            result += ' [%s]' % ','.join(self.extras)
        return result

    def __repr__(self):
        return 'EntryPoint.parse(%r)' % str(self)


class PathMetadata(object):
    """
    A metadata provider that reads the metadata files found within the
    provided metadata directory (typically an ``.egg-info`` or a
    ``.dist-info`` directory located at the distribution location);
    mirrors the interface of ``pkg_resources.PathMetadata`` as used by
    this framework.
    """

    def __init__(self, location, metadata_dir):
        self.location = location
        self.metadata_dir = metadata_dir

    def has_metadata(self, name):
        return os.path.isfile(os.path.join(self.metadata_dir, name))

    def get_metadata(self, name):
        path = os.path.join(self.metadata_dir, name)
        if not os.path.isfile(path):
            raise IOError("metadata file '%s' not found" % name)
        with open(path, encoding='utf-8') as fd:
            return fd.read()


class Distribution(object):
    """
    A distribution that is installed on the file system, or one that is
    simply mocked up; mirrors the interface of
    ``pkg_resources.Distribution`` as used by this framework.
    """

    def __init__(self, location=None, metadata=None, project_name=None,
                 version=None):
        self.location = location
        self.metadata = metadata
        # mirror the normalization performed by pkg_resources.
        self.project_name = safe_name(project_name or 'Unknown')
        self.version = version

    @property
    def key(self):
        return self.project_name.lower() if self.project_name else None

    @property
    def egg_info(self):
        if getattr(self, '_egg_info', None) is not None:
            return self._egg_info
        if self.metadata is None:
            return None
        return getattr(self.metadata, 'metadata_dir', None)

    @egg_info.setter
    def egg_info(self, value):
        self._egg_info = value

    def has_metadata(self, name):
        if self.metadata is None:
            return False
        return self.metadata.has_metadata(name)

    def get_metadata(self, name):
        if self.metadata is None:
            raise IOError("no metadata provider for '%s'" % self)
        return self.metadata.get_metadata(name)

    def get_entry_map(self, group=None):
        if group is not None:
            return self._parse_entry_points().get(group, {})
        return self._parse_entry_points()

    def _parse_entry_points(self):
        if not self.has_metadata('entry_points.txt'):
            return {}
        parser = ConfigParser(delimiters=('=',), interpolation=None)
        parser.optionxform = str
        try:
            parser.read_string(self.get_metadata('entry_points.txt'))
        except Exception:
            logger.error(
                "failed to parse entry_points.txt for '%s'", self)
            return {}
        result = {}
        for group in parser.sections():
            mapping = result.setdefault(group, {})
            for name, value in parser.items(group):
                try:
                    entry_point = EntryPoint.parse(
                        '%s = %s' % (name, value), group)
                except ValueError:
                    logger.warning(
                        "ignoring invalid entry point '%s = %s' for '%s'",
                        name, value, self)
                    continue
                entry_point.dist = self
                mapping[name] = entry_point
        return result

    def requires(self, extras=()):
        if self.has_metadata('requires.txt'):
            return _parse_requires_txt(
                self.get_metadata('requires.txt'), extras)
        for name in ('METADATA', 'PKG-INFO'):
            if self.has_metadata(name):
                return _parse_metadata_requires(
                    self.get_metadata(name), extras)
        return []

    def as_requirement(self):
        if self.version is None:
            return Requirement.parse(self.project_name)
        return Requirement.parse('%s==%s' % (self.project_name, self.version))

    def __str__(self):
        return '%s %s' % (
            self.project_name, self.version or '[unknown version]')

    def __repr__(self):
        if self.location:
            return '%s (%s)' % (str(self), self.location)
        return str(self)


class WorkingSet(object):
    """
    A collection of distributions discovered from a list of path
    entries; mirrors the interface of ``pkg_resources.WorkingSet`` as
    used by this framework.
    """

    def __init__(self, entries=None):
        self.entries = []
        self.entry_keys = {}
        self.by_key = {}
        for entry in (sys.path if entries is None else entries):
            self.add_entry(entry)

    def add_entry(self, entry):
        for dist in _distributions_on_path(entry):
            self.add(dist, entry)

    def add(self, dist, entry=None, insert=True, replace=False):
        key = dist.key
        if key is None:
            return
        if key in self.by_key and not replace:
            return
        self.by_key[key] = dist
        if entry is None:
            entry = dist.location
        if entry is not None:
            self.entry_keys.setdefault(entry, []).append(dist)
            if insert and entry not in self.entries:
                self.entries.append(entry)

    def find(self, req):
        dist = self.by_key.get(req.key)
        if dist is None:
            return None
        if dist not in req:
            raise VersionConflict(dist, req)
        return dist

    def iter_entry_points(self, group, name=None):
        for dist in self:
            for entry_point in dist.get_entry_map(group).values():
                if name is None or name == entry_point.name:
                    yield entry_point

    def resolve(self, requirements, env=None, installer=None):
        # The dependencies are processed breadth-first, mirroring the
        # ordering behaviour of the pkg_resources implementation.
        requirements = list(requirements)[::-1]
        # set of processed requirements
        processed = set()
        # key -> dist
        best = {}
        to_activate = []
        while requirements:
            req = requirements.pop(0)
            if req in processed:
                # ignore cyclic or redundant dependencies
                continue
            if not _marker_applies(req.marker, req.extras):
                continue
            dist = best.get(req.key)
            if dist is None:
                dist = self.find(req)
                if dist is None:
                    raise DistributionNotFound(req)
                best[req.key] = dist
                to_activate.append(dist)
            if dist not in req:
                raise VersionConflict(dist, req)
            # push the new requirements onto the stack
            requirements.extend(dist.requires(extras=req.extras)[::-1])
            processed.add(req)
        return to_activate

    def __iter__(self):
        seen = set()
        for entry in self.entries:
            for dist in self.entry_keys.get(entry, []):
                if dist.key in seen:
                    continue
                seen.add(dist.key)
                yield dist


def _distributions_on_path(entry):
    """
    Yield the Distribution objects for the distribution metadata
    directories found on the given path entry.
    """

    if not entry or not os.path.isdir(entry):
        return
    try:
        names = os.listdir(entry)
    except OSError:
        return
    for name in sorted(names):
        for suffix in META_SUFFIXES:
            if not name.endswith(suffix):
                continue
            metadata_dir = os.path.join(entry, name)
            if not os.path.isdir(metadata_dir):
                break
            yield _make_distribution(entry, metadata_dir)
            break


def _make_distribution(location, metadata_dir):
    basename = os.path.basename(metadata_dir)
    for suffix in META_SUFFIXES:
        if basename.endswith(suffix):
            stem = basename[:-len(suffix)]
            break
    else:
        raise ValueError("unexpected metadata directory %r" % metadata_dir)
    project_name = stem
    version = None
    if '-' in stem:
        project_name, version = stem.rsplit('-', 1)
    provider = PathMetadata(location, metadata_dir)
    # refine the values using the metadata files, when available.
    for metadata_name in ('METADATA', 'PKG-INFO'):
        if provider.has_metadata(metadata_name):
            msg = email.message_from_string(
                provider.get_metadata(metadata_name))
            project_name = msg.get('Name') or project_name
            version = msg.get('Version') or version
            break
    return Distribution(
        location=location, metadata=provider,
        project_name=project_name, version=version)


def _marker_applies(marker, extras):
    if marker is None:
        return True
    environments = [None]
    environments.extend({'extra': str(extra)} for extra in extras)
    for environment in environments:
        try:
            if marker.evaluate(environment):
                return True
        except Exception:
            continue
    return False


def _parse_requires_txt(content, extras=()):
    result = []
    section = None
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1].strip()
            continue
        if section is not None and section not in extras:
            continue
        try:
            requirement = Requirement.parse(line)
        except ValueError:
            logger.warning("ignoring invalid requirement line '%s'", line)
            continue
        if section is None and not _marker_applies(requirement.marker, extras):
            continue
        result.append(requirement)
    return result


def _parse_metadata_requires(content, extras=()):
    result = []
    msg = email.message_from_string(content)
    for line in msg.get_all('Requires-Dist') or []:
        try:
            requirement = Requirement.parse(line)
        except ValueError:
            logger.warning("ignoring invalid requirement line '%s'", line)
            continue
        if not _marker_applies(requirement.marker, extras):
            continue
        result.append(requirement)
    return result


# The default working set, containing the distributions found on the
# current sys.path entries.
working_set = WorkingSet()


def resource_filename(package_or_requirement, resource_name):
    """
    Resolve the path to a resource, given either a Requirement (which
    will be resolved against the default working set) or the name of an
    importable module, and the name of the resource within it.  Mirrors
    the behaviour of ``pkg_resources.resource_filename`` for the usage
    patterns of this framework.
    """

    if isinstance(package_or_requirement, Requirement):
        dist = working_set.find(package_or_requirement)
        if dist is None:
            raise DistributionNotFound(package_or_requirement)
        base = dist.location or ''
    else:
        module = importlib.import_module(package_or_requirement)
        module_file = getattr(module, '__file__', None)
        if module_file:
            base = os.path.dirname(module_file)
        else:
            module_paths = getattr(module, '__path__', None) or ('',)
            base = next(iter(module_paths), '')
    if resource_name:
        return os.path.join(base, *resource_name.split('/'))
    return base

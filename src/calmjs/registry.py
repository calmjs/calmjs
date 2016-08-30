# -*- coding: utf-8 -*-
"""
Registry of all registries for calmjs.

This module provides the implementation for working with the entry point
group ``calmjs.registry``, where it will be able to instantiate and
cache registries for the rest of the calmjs framework.

Typically, usage is done through this::

    >>> from calmjs.registry import get
    >>> calmjs_module = get('calmjs.module')
    >>> calmjs_module  # doctest: +ELLIPSIS
    <calmjs.module.ModuleRegistry object ...>
    >>> calmjs_module.iter_records()  # doctest: +ELLIPSIS
    <generator object ...>

The iter_records is typically used by the other parts of the calmjs
framework to produce configuration files and/or transpile the source
into the usable final form.
"""

from __future__ import absolute_import

from logging import getLogger
from calmjs.base import BaseRegistry

logger = getLogger(__name__)


class Registry(BaseRegistry):

    def _init(self):
        """
        Turn the records into actual usable keys.
        """

        self._entry_points = {
            entry_point.name: entry_point
            for entry_point in self.raw_entry_points
        }
        # No pre-caching for below, let the get_record load things into
        # records on-demand.

    def get_record(self, name):
        if name in self.records:
            # maybe do some other sanity check if pedantic.
            logger.debug('found existing registry %s', name)
            return self.records[name]

        entry_point = self._entry_points.get(name)
        if not entry_point:
            return

        try:
            cls = entry_point.load()
        except ImportError:
            return

        logger.debug('registering %s from %s', entry_point, entry_point.dist)
        try:
            self.records[name] = cls(name)
        except Exception:
            logger.exception(
                '%s does not lead to a valid registry constructor',
                entry_point,
            )
            return
        return self.records[name]


# Initialize the root registry instance
_inst = Registry(__name__)  # __name__ == calmjs.registry
_inst.records[__name__] = _inst  # tie the knot, self-hosting.
get = _inst.get

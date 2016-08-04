# -*- coding: utf-8 -*-
"""
Generic registry loader

This module simply provides a function to get registries that have been
registered through its standardized, inherited initialize classmethod
constructor.
"""

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
get = _inst.get_record

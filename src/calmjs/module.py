# -*- coding: utf-8 -*-
"""
Registry framework for calmjs

This intends to be an extensible, pluggable registry system for the
calmjs infrastructure that leverages on the underlying setuptools entry
point system.
"""

from logging import getLogger
from pkg_resources import EntryPoint

from calmjs.base import BaseModuleRegistry
from calmjs.indexer import mapper_es6 as default_loader

logger = getLogger(__name__)


class ModuleRegistry(BaseModuleRegistry):
    """
    A registry that tracks all JavaScript modules that have been shipped
    with Python modules within the running Python environment.
    """

    entry_point_name = __name__

    def _init(self):
        self.default_loader = default_loader
        self.module_map = {}

    def _register_entry_point_module(self, entry_point, module):
        """
        """

        if entry_point.extras:
            # grab the first extras and try to import that as loader
            # TODO figure out if this is even a good idea.
            target = ':'.join(entry_point.extras[0].rsplit('.', 1))
            try:
                loader = EntryPoint.parse('dummy = ' + target).resolve()
            except Exception as e:
                logger.warning(
                    'The extra section defined in entry point `%s` for module '
                    '`%s` could not be used as a JavaScript source loader '
                    'due to the following exception: %s: %s; '
                    'skipping registration for this module.',
                    entry_point, module.__name__, e.__class__.__name__, e,
                )
                return
        else:
            loader = default_loader

        self.module_map[module.__name__] = loader(module)

# Create an initialized instance of all the things.  This can take some
# time to import if there are many entry points.  Generally this module
# is not going to be loaded in typical usage so leave this here for now.
registry = ModuleRegistry.initialize(__name__)

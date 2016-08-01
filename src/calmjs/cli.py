# -*- coding: utf-8 -*-
import logging
import json
import re
from os.path import exists

from subprocess import check_output
from subprocess import call

from calmjs.npm import PACKAGE_JSON
from calmjs.dist import flatten_package_json

__all__ = [
    'get_node_version', 'get_npm_version', 'npm_install',
]

logger = logging.getLogger(__name__)

version_expr = re.compile('((?:\d+)(?:\.\d+)*)')

NODE_PATH = 'NODE_PATH'
NODE = 'node'
NPM = 'npm'


def _get_bin_version(bin_path, version_flag='-v', _from=None, _to=None):
    try:
        version_str = version_expr.search(
            check_output([bin_path, version_flag]).decode('ascii')
        ).groups()[0]
        version = tuple(int(i) for i in version_str.split('.'))
    except OSError:
        logger.warning('Failed to execute %s', bin_path)
        return None
    except:
        logger.exception(
            'Encountered unexpected error while trying to find version of %s:',
            bin_path
        )
        return None
    logger.info('Found %s version %s', bin_path, version_str)
    return version


class Cli(object):

    indent = 4

    def __init__(self, node_bin=NODE, npm_bin=NPM,
                 node_path=None):
        """
        Optional Arguments:

        node_bin
            Path to node binary.  Defaults to ``node``.
        npm_bin
            Path to npm binary.  Defaults to ``npm``.
        node_path
            Overrides NODE_PATH environment variable.
        """

        self.node_path = node_path
        self.node_bin = node_bin
        self.npm_bin = npm_bin

    def get_node_version(self):
        return _get_bin_version(self.node_bin, _from=1)

    def get_npm_version(self):
        return _get_bin_version(self.npm_bin)

    def npm_install(self, package_name=None):
        """
        Installs node_modules into the current working directory for the
        specific package.  With an already available ``package.json``
        file, the init process will be skipped.
        """

        if package_name and not exists(PACKAGE_JSON):
            package_json = flatten_package_json(
                package_name, filename=PACKAGE_JSON)

            with open(PACKAGE_JSON, 'w') as fd:
                json.dump(package_json, fd, indent=self.indent)

        kw = {}
        env = {}

        if self.node_path:
            env[NODE_PATH] = self.node_path

        if env:
            kw['env'] = env

        call([self.npm_bin, 'install'], **kw)


_inst = Cli()
get_node_version = _inst.get_node_version
get_npm_version = _inst.get_npm_version
npm_install = _inst.npm_install

# -*- coding: utf-8 -*-
import logging
import json
import os
import re
from os.path import exists
from os.path import isdir
from os.path import join
from shutil import rmtree

from subprocess import check_output
from subprocess import call

from calmjs.npm import PACKAGE_JSON

__all__ = [
    'get_node_version', 'get_npm_version', 'npm_install',
    'make_package_json',
]

logger = logging.getLogger(__name__)

version_expr = re.compile('((?:\d+)(?:\.\d+)*)')

PACKAGE_JSON = 'package.json'
NODE = 'node'
NPM = 'npm'


def make_package_json(**config):
    defaults = {
        "name": "calmjs-generated-stub",
        "version": "0.0.1",
        "main": "calmjs.bundle.js",
        "readme": "calmjs generated stub package",
        "repository": {
        },
        "dependencies": {
        },
        "devDependencies": {
            "chai": "^2.3.0",
            "coveralls": "~2.11.2",
            "extend": "~2.0.1",
            "grunt": "~0.4.5",
            "grunt-cli": "~0.1.13",
            "grunt-contrib-copy": "~0.8.0",
            "grunt-contrib-jshint": "~0.11.2",
            "grunt-contrib-less": "~1.0.1",
            "grunt-contrib-requirejs": "~0.4.4",
            "grunt-contrib-uglify": "~0.9.1",
            "grunt-contrib-watch": "~0.6.1",
            "grunt-karma": "~0.10.1",
            "grunt-sed": "~0.1.1",
            "karma": "~0.12.31",
            "karma-chai": "^0.1.0",
            "karma-expect": "~1.1.2",
            "karma-chrome-launcher": "~0.1.8",
            "karma-coverage": "~0.3.1",
            "karma-firefox-launcher": "~0.1.4",
            "karma-junit-reporter": "~0.2.2",
            "karma-mocha": "~0.1.10",
            "karma-phantomjs-launcher": "~0.2.1",
            "karma-requirejs": "~0.2.2",
            "karma-sauce-launcher": "~0.2.10",
            "karma-script-launcher": "~0.1.0",
            "karma-sinon": "~1.0.5",
            "karma-spec-reporter": "0.0.19",
            "lcov-result-merger": "~1.0.2",
            "less": "~1.7.0",
            "mocha": "~2.2.4",
            "phantomjs": "~2.1.1",
            "requirejs": "~2.1.17",
            "requirejs-text": "~2.0.12",
            "sinon": "~1.17.4",
        },
    }
    defaults.update(config)
    return defaults


def _get_bin_version(bin_path, version_flag='-v', _from=None, _to=None):
    try:
        _slice = slice(_from, _to)
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

        if node_path:
            os.environ['NODE_PATH'] = node_path

        self.node_bin = node_bin
        self.npm_bin = npm_bin

    def get_node_version(self):
        return _get_bin_version(self.node_bin, _from=1)

    def get_npm_version(self):
        return _get_bin_version(self.npm_bin)

    def npm_install(self, package_json=None):
        """
        Installs node_modules into the current working directory.

        Will be nice if there's a clean way to redirect this to some
        other directory.
        """

        if not exists(PACKAGE_JSON):
            if package_json is None:
                package_json = make_package_json()

            with open(PACKAGE_JSON, 'w') as fd:
                json.dump(package_json, fd)

        call([self.npm_bin, 'install'])

_inst = Cli()
get_node_version = _inst.get_node_version
get_npm_version = _inst.get_npm_version
npm_install = _inst.npm_install

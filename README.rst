calmjs
======

A toolchain for working with JavaScript from a Python-based environment,
from the definition of modules, to import system and the deployment of
the final module package for distribution in a way that is painless for
developers, integrators and end-users to consume.

.. image:: https://travis-ci.org/calmjs/calmjs.svg?branch=master
    :target: https://travis-ci.org/calmjs/calmjs
.. image:: https://coveralls.io/repos/github/calmjs/calmjs/badge.svg?branch=master
    :target: https://coveralls.io/github/calmjs/calmjs?branch=master

Introduction
============

This package provides a toolchain that builds JavaScript files from
available Python packages into a single bundle.


Features
--------

The core of the package is a toolchain that will load and compile all
registered JavaScript files within a python (virtual) environment and
bundle everything into a single file.  It also provides helper utilities
that set up a working nodejs environment for bunding other dependencies
reachable through npm, and also sets up test environments for running
JavaScript unit/functional/integration tests.

Currently, with the usage of calmjs setuptools command hooks, it is
possible to declare npm dependencies in a ``setup.py`` file by setting a
``package_json`` attribute to the ``setup`` call within that file.
Through the use of ``setup.py npm --init``, a ``package.json`` will be
generated from the dependencies declared not only the current package,
but also from all Python module dependencies that have been been
declared.  The dependency declaration within the ``package.json`` will
of course be flattened as per Python's module/import/distutils system,
thus the resulting dependencies required by all npm packages will be
installed alongside the top level Python package.

Installation
------------

Currently under development, please install by cloning this repository
and run ``python setup.py develop`` within your environment, or follow
your framework's method on installation of development packages.


Contribute
----------

- Issue Tracker: https://github.com/calmjs/calmjs/issues
- Source Code: https://github.com/calmjs/calmjs


License
-------

The project is licensed under the GPLv2 or later.

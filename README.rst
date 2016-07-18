calmjs
======

A utility package that provides a set of tools that allows JavaScript to
be used more easily alongside with Python.

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

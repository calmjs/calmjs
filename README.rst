calmjs
======

A framework for building toolchains and machineries for working with
JavaScript from the Python environment.

.. image:: https://travis-ci.org/calmjs/calmjs.svg?branch=master
    :target: https://travis-ci.org/calmjs/calmjs
.. image:: https://coveralls.io/repos/github/calmjs/calmjs/badge.svg?branch=master
    :target: https://coveralls.io/github/calmjs/calmjs?branch=master

Introduction
============

At its core, calmjs provides a set of extension to |setuptools|_ that
assists with the tracking and management of dependencies of JavaScript
packages (such as ones through |npm|_) for a given Python package.  It
also provides a number of base classes that can be used to build custom
toolchains that implement different strategies for managing and
compiling required JavaScript code and related assets into the
deployment bundle file that an application server may use.  Related
packages that make use of this framework implementing the most commonly
used patterns for the various use cases will become available to
facilitate painless and easy deployment of JavaScript and assets to
servers for developers and integrators to use.  These use cases will
include the management of testing frameworks, to the bundling of APM
modules.

.. |setuptools| replace:: ``setuptools``
.. |npm| replace:: ``npm``
.. _setuptools: https://pypi.python.org/pypi/setuptools
.. _npm: https://www.npmjs.com/

The name calmjs was originally derived from the steps in the first
iteration of the toolchain which involves the steps compile, assemble,
and linkage into a module of JavaScript using the namespace from the
host Python package.  The logo (whenever this can be gotten around to)
will involve a bunny rabbit, ears represented by the `m` letter.  This
is choosen for their dietary habits, which is akin to how JavaScript is
typically worked into a state that resembles a usable level.


Features
--------

Record and generate ``package.json`` for consumption by |npm|_
    This is done through the usage of |setuptools|_ command hooks, it is
    possible to declare npm package dependencies in a ``setup.py`` file
    by setting a ``package_json`` attribute to the ``setup`` call within
    that file.  These dependencies will be persisted as egg-info
    metadata which will be usable by other packages depending on the
    declaring one; their dependencies will naturally be layered on top
    of all their parents' ``package.json`` as Python and |setuptools|_
    support a flat dependency structure.  The packages from which the
    tool is invoked (this can be done typically through ``setup.py npm
    --init``) will be able to override all the ``dependencies`` /
    ``devDependencies`` that may have been specified by their parent
    packages.  Naturally, this package should be usable by any other
    compatible package managers and/or repositories.

Better integration of JavaScript toolchains with Python environment
    This basically is a framework for building toolchains for working
    with JavaScript that integrates well with existing Python packages
    and environment.

    There are no limitations as to how or what this can be done, as this
    is left as an implementation detail.  For an example (when this is
    done) please refer to the ``calmjs.rjs`` package.

    Generally, toolchains can be built to find and load all Python
    packages that have any JavaScript source files, and those will be
    extracted, go through the appropriate transpilers (if any) in order
    to build a deployable bundle/minified file.  Test harnesses can be
    set up to aid with running of unit tests, functional testing and
    naturally the final integration tests needed for a successful
    deployment.


Installation
------------

Currently under development, please install by cloning this repository
and run ``python setup.py develop`` within a working Python environment,
or follow the local framework or operating system's default method on
installation of development packages that have pulled this package in.


Usage
-----

If a package wish to declare dependencies for |npm|_ packages, it may do
something like this in its ``setup.py``:

.. code:: python

    from setuptools import setup

    package_json = {
        "dependencies": {
            "jquery": "~3.0.0",
            "underscore": "~1.8.0",
        }
    }

    setup(
        name='example.package',
        ...
        install_requires=[
            'calmjs',
            ...
        ],
        package_json=package_json,
        ...
    )


Documentation on how to extend the Toolchain class to support use cases
will need to be done, though the focus right now is to provide a working
``calmjs.rjs`` package.


Dealing with |npm|_ dependencies with Python package dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Remember, flat is better than nested.  So all ``dependencies`` (and
``devDependencies``) declared can be overridden by subsequent packages,
and doing so flattens the dependencies for the final package to consume,
with the desired toolchain to make use of the declared information to
generate their JavaScript bundle.

Of course, if the nested style of packages and dependency in the same
style as npm is desired, no one is forced to use this, they are free to
split their packages up to Python and JavaScript bits and have them be
deployed and hosted both pypi (for pip) and npm (respectively) and then
figure out how to bring them back together in a coherent manner.  Don't
ask the author how this option is easier or better.


Contribute
----------

- Issue Tracker: https://github.com/calmjs/calmjs/issues
- Source Code: https://github.com/calmjs/calmjs


License
-------

The project is licensed under the GPLv2 or later.

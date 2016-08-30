calmjs
======

A Python framework for building toolchains and utilities for working
with the JavaScript/Node.js ecosystem.  The JavaScript source files can
be sourced from packages from any supported Node.js based repositories
or embedded in Python packages.  This framework strives to make the
usage of all these JavaScript source file in a consistent, well
integrated manner within a Python environment.  Locations, dependencies
and related metadata related to the JavaScript sources at hand will be
defined within a common framework, resulting in the accessibility
through a common set of tools.  This ensures the consistent
reproducibility during usage within a continuous integration and/or
deployment environment.

.. image:: https://travis-ci.org/calmjs/calmjs.svg?branch=master
    :target: https://travis-ci.org/calmjs/calmjs
.. image:: https://coveralls.io/repos/github/calmjs/calmjs/badge.svg?branch=master
    :target: https://coveralls.io/github/calmjs/calmjs?branch=master


Introduction
------------

In essence, ``calmjs`` provides a set of extension to |setuptools|_ that
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

The name ``calmjs`` was originally derived from the steps in the first
iteration of the toolchain which involves the steps compile, assemble,
and linkage into a module of JavaScript using the namespace from the
host Python package.  The `m` in the logo is the ear of a rabbit.  The
reason this animal is chosen as the mascot for this project is because
of their dietary habits, as it's analogous to how JavaScript code is
typically turned into a minimally usable level by other tools and
framework.


Features
--------

Integration with Node.js based package managers (default: ``npm``)
    Through ``setuptools`` command hooks, ``calmjs`` provides Python
    packages with the ability to declare and manage manifest definition
    files for Node.js based package management systems (e.g. such as
    ``package.json`` for ``npm``).  In the typical use case, this means
    the declaration of ``dependencies`` or ``devDependencies`` for the
    JavaScript packages needed by a given Python package can be tracked,
    all within the ``setuptools`` framework.

    The other part of this infrastructure is that these declarations
    follow the Python package dependency graph.  Developers and users
    can make use of the ``calmjs`` console command entry point, or
    through ``setuptools``, to generate a manifest file to facilitate
    the installation of Node.js packages required by the Python packages
    within the completed application stack, tailored for all the
    packages at hand.

Export JavaScript code out of Python packages with the same namespace
    A given Python package that included associated JavaScript code
    within the same module and namespace structure alongside with Python
    modules within the source tree, will be able to declare those code
    as JavaScript modules under the exact same namespace through
    ``setuptools`` entry points.

    These declarations will be available through registries exposed by
    ``calmjs`` for other packages to turn those declarations through the
    API available into working JavaScript code following the same
    declared module and namespace structures, though the default module
    registry will make use of the ``/`` character as the separator for
    the names due to established naming conventions in JavaScript (and
    in ES6 towards the future).

    Other tools that works with the ``calmjs`` framework can then make
    use of these raw JavaScript source files, turning them into actual
    usable Node.js modules for local consumption, or AMD modules for
    consumption over the web.  This leads to...

Better integration of JavaScript toolchains into Python environments
    This is achieved by providing a framework for building toolchains
    for working with tools written in JavaScript for JavaScript that
    integrates properly with existing Python packages and environment.

    There are no limitations as to how or what this can be done, as this
    is left as an implementation detail.  For an example (when this is
    done) please refer to the ``calmjs.rjs`` package, which allows the
    production of AMD modules from JavaScript packages embedded inside
    Python packages.

    Generally, toolchains can be built to find and load all Python
    packages that have any JavaScript source files, and those will be
    extracted, go through the appropriate transpilers (if any) in order
    to build a deployable bundle/minified file.  Test harnesses can be
    set up to aid with running of unit tests, functional testing and
    naturally the final integration tests needed for a successful
    deployment.

Well-defined modular architecture to ensure code reuse and extensibility
    The features described so far are built upon a foundation of generic
    classes and modules, so that the support for additional JavaScript
    tools or custom process for handling transpilation can be as simple
    as creating a new module for a couple classes with additional
    parameters with the relevant ``setuptools`` entry points.

    In fact, ``calmjs`` out of the box only ships with just the core
    framework plus the ``npm`` interfacing part, with the support for
    tools like ``bower`` or ``r.js`` as completely separate packages
    such that projects or sites that do not need those functionality can
    simply not have them installed.


Installation
------------

Currently under development, please install by cloning this repository
and run ``python setup.py develop`` within a working Python environment,
or follow the local framework or operating system's default method on
installation of development packages that have pulled this package in.

Testing
~~~~~~~

To ensure that the ``calmjs`` installation is functioning correctly, the
built-in testsuite can be executed by the following:

.. code:: sh

    $ python -m unittest calmjs.tests.make_suite

If there are failures, please file an issue on the issue tracker with
the full traceback with the method of installation.


Usage
-----

Declare a ``package.json`` for a given Python package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If a package wish to declare dependencies for ``npm`` packages, it may
do something like this in its ``setup.py``:

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

Running ``setup.py install`` will write that ``package_json`` fragment
into the package's egg-info metadata section, provided that it is a
valid JSON string or a dictionary without incompatible data types.

All packages that ultimately depending on this ``example.package`` will
have the option to inherit this ``package.json`` egg-info metadata.
One way to do this is through that package's ``setup.py``.  By invoking
``setup.py npm --init`` from there, a new ``package.json`` will be
written to the current directory as if running ``npm init`` with all the
dependencies declared through the Python package dependency tree for the
given Python package.

Declare explicit dependencies on paths inside ``node_modules``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Given that the dependencies on specific versions of packages sourced
from ``npm`` is explicitly specified, build tools will benefit again
from explicit declarations on files needed from those packages.  Namely,
the compiled packages could be declared in the ``extras_calmjs`` section
in JSON string much like ``package_json``, like so:

.. code:: python

    extras_calmjs = {
        'node_modules': {
            'jquery': 'jquery/dist/jquery.js',
            'underscore': 'underscore/underscore.js',
        },
    }

    setup(
        name='example.package',
        ...
        extras_calmjs=extras_calmjs,
        ...
    )

Since ``node_modules`` is declared to be an ``extras_key``, conflicts
with existing declarations in other packages within the environment will
be merged like how dependencies sections declared in ``package_json``
(see below).

Please do note that complete paths must be declared (note that the
``.js`` filename suffix is included in the example); directories can
also be declared.  However, as these declarations are done from within
Python, explicit, full paths are required thus it is up to downstream
integration packages to properly handle and/or convert this into the
conventions that standard Node.js tools might expect (i.e. where the
``.js`` filename suffix is omitted).

Export JavaScript code from Python packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Furthering the previous example, if the files and directories inside
``example.package`` are laid out like so::

    .
    ├── example
    │   ├── __init__.py
    │   └── package
    │       ├── __init__.py
    │       ├── content.py
    │       ├── form.py
    │       ├── ui.js
    │       ├── ui.py
    │       └── widget.js
    └── setup.py

To declare the JavaScript source files within ``./example/package``
as JavaScript modules through ``calmjs``, an entry point can be declared
like so in the ``setup.py`` file:

.. code:: python

    setup(
        ...
        entry_points="""
        ...
        [calmjs.module]
        example.package = example.package
        """
        ...
    )

The default method will expose the two source files with the following
names::

    - 'example/package/ui'
    - 'example/package/widget'

For some projects, it may be undesirable to permit this automated method
to extract all the available JavaScript source files from within the
given Python module.

To get around this, it is possible to declare new module registries
through the ``calmjs`` framework.  Provided that the ``ModuleRegistry``
subclass was set up correctly to generate the desired modules from a
given package, simply declare this as a ``calmjs.registry`` entry point
like so:

.. code:: python

    setup(
        ...
        entry_points="""
        ...
        [calmjs.registry]
        example.module = example.package.registry:ExampleModuleRegistry
        """
        ...
    )

Then to use simply replace ``calmjs.module`` with the name of the
registry that was just declared.

.. code:: python

    setup(
        ...
        entry_points="""
        ...
        [example.module]
        example.package = example.package
        """
        ...
    )

Within the ``calmjs`` framework, tools can be explicitly specified to
capture modules from any or all module registries registered to the
framework.  One other registry was also defined.  If the entry point
was declared like so:

.. code:: python

    setup(
        ...
        entry_points="""
        ...
        [calmjs.module.pythonic]
        example.package = example.package
        """
        ...
    )

The separator for the namespace and the module will use the ``.``
character instead of ``/``.  However given that the ``.`` character is
a valid name for a JavaScript module, the usage of this may create
issues with certain JavaScript tools.  However, AMD based module systems
can generally deal with ``.`` without issues so using those may end up
resulting in somewhat more Python-like feel when dealing with imports
while using JavaScript, though at a slight cost of whatever standards
compliance with it.

Command line utility
~~~~~~~~~~~~~~~~~~~~

It is possible to make use of the ``package.json`` generation
capabilities from outside of the ``setuptools`` extensions.  Users can
easily do the same through the built-in ``calmjs`` utility, like so:

.. code:: sh

    $ calmjs --help
    usage: calmjs [-h] [-v] [-q] [-d] <command> ...

    calmjs runtime collection

    positional arguments:
      <command>
        npm          npm compatibility helper

    optional arguments:
      -h, --help     show this help message and exit
      -v, --verbose  be more verbose
      -q, --quiet    be more quiet

The above lists the output of a default ``calmjs`` installation.
Packages that registers the appropriate entry points will be able to
provide additional commands to that list for usage within the framework.

Naturally, the same ``--init`` functionality shown above with the
``setuptools`` framework is available, however package names can be
supplied for generating the target ``package.json`` file from anywhere
on the filesystem, provided that the Python environment has all the
required packages installed.  For instance, if ``calmjs.rjs`` is
installed, this can be invoked to view the ``package.json`` that would
be generated:

.. code:: sh

    $ calmjs -v npm --view calmjs.rjs
    2016-08-24 19:08:23,097 INFO calmjs.cli generating a flattened 'package.json' for 'calmjs.rjs'
    {
        "dependencies": {
            "requirejs": "~2.1.17"
        },
        "devDependencies": {
            "grunt-contrib-requirejs": "~0.4.4",
            "karma-requirejs": "~0.2.2"
        },
        "name": "calmjs.rjs"
    }

For detailed usage, please refer to the inline help, accessible via
``--help``.  Do note, if help is needed for the specific command, the
command must be supplied before the ``--help`` argument.  For instance,
try ``calmjs npm --help``.

Developers who wish to provide JavaScript based tools through this
infrastructure can simply extend the ``calmjs.runtime.DriverRuntime``
class, and the exact instructions will be available in the developer
guide (when it is written).

Toolchain
~~~~~~~~~

Documentation on how to extend the Toolchain class to support use cases
will need to be done, though the focus right now is to provide a working
``calmjs.rjs`` package.

Dealing with ``npm`` dependencies with Python package dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Remember, flat is better than nested.  So all ``dependencies`` (and
``devDependencies``) declared by any upstream Python package will be
automatically inherited by all its downstream packages, but they have
the option to override it with whatever they want through the mechanism
as described above.  They can set a JavaScript package to whatever
versions desired, or even simply remove that dependency completely by
setting the version to ``None``.

Through this inheritance mechanism whenever an actual ``package.json``
is needed to be generated for final consumption for a given Python
package, the dependencies are flattened for consumption by the
respective JavaScript package managers, or by the desired toolchain to
make use of the declared information to generate the desired JavaScript
bundle.

Of course, if the nested style of packages and dependency in the same
style as npm is desired, no one is forced to use this, they are free to
split their packages up to Python and JavaScript bits and have them be
deployed and hosted both pypi (for pip) and npm (respectively) and then
figure out how to bring them back together in a coherent manner.  Don't
ask the author how this option is easier or better.


Troubleshooting
---------------

Here may be some common issues with usage of ``calmjs``

Runtime reporting 'unrecognized arguments:' on recognized ones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For instance, if the ``calmjs`` binary was executed like so resulting in
error message may look like this:

.. code:: sh

    $ calmjs npm --install calmjs.dev -v
    usage: calmjs [-h] [-v] [-q] [-d] <command> ...
    calmjs: error: unrecognized arguments: -v

This means that the ``-v`` is unrecognized by the subcommand (i.e. the
``calmjs npm`` command) as it was placed after.  Unfortunately there are
a number of bugs in ``argparse`` module that behaves differently across
different python versions that made it very difficult to consistently
provide this information.  There are workarounds made in the
``calmjs.runtime`` module so this situation should not arise, however if
it does, please file an issue on the tracker.

CRITICAL calmjs.runtime terminating due to a critical error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If ``calmjs`` encounters any unexpected situation, it may abort like so:

.. code:: sh

    $ calmjs npm --install calmjs.dev
    CRITICAL calmjs.runtime terminating due to a critical error

If no useful ERROR message is listed before, please try running again
using a debug flag (either ``-d`` or ``--debug``).

.. code:: sh

    $ calmjs -d npm --install calmjs.dev
    CRITICAL calmjs.runtime terminating due to exception
    Traceback (most recent call last):
    ...

Specifying the debug flag twice will enable the ``post_mortem`` mode,
where a debugger will be fired at the point of failure.  Authors of
runtime modules may find this useful during their development cycles.

ERROR bad 'calmjs.runtime' entry point
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ImportError
    This is typically caused by improper removal of locally installed
    packages that had a entry point registered, or that an addon package
    to ``calmjs`` has registered bad entry points.  Either reinstall the
    listed package again or fully uninstall or remove its files.

bad entry point
    This is caused by packages defining malformed entry point.  The
    name of the package triggering this error will be noted in the log;
    the error may be reported to its developer.


Contribute
----------

- Issue Tracker: https://github.com/calmjs/calmjs/issues
- Source Code: https://github.com/calmjs/calmjs


License
-------

The ``calmjs`` project is licensed under the GPLv2 or later.

calmjs
======

A framework for building toolchains and machineries for working with
JavaScript from the Python environment.

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

Manage dependencies on JavaScript modules (hosted by ``npm`` or others).
    By providing ``setuptools`` command hooks, ``calmjs`` enables the
    management of the ``package.json`` for Python modules.  In the
    typical use case, this means the management of ``dependencies`` /
    ``devDependencies`` for the declaration of required JavaScript
    packages needed by a given Python project.

    The command hooks also have the ability to follow through the list
    of Python package requirements to generate a comprehensive
    ``package.json`` for a current project.  This means all upstream
    dependencies on JavaScript packages will also be used when
    generating the final ``package.json`` needed by any given project.

    In other words, subsequent Python packages can readily generate and
    reuse its parent(s) ``package.json`` file with ease.

Expose JavaScript code in a Python module as proper namespace modules
    A given Python package that may have included JavaScript code
    associated for that project will be able to declare those code as
    JavaScript modules with the exact same namespace through
    ``setuptools`` entry points.

    These declarations will be available through registries exposed by
    ``calmjs`` for other packages to turn those declarations through the
    API available into working JavaScript code following the same
    declared module structures.

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
into the package's egg-info metadata section.

All packages that ultimately depending on this ``example.package`` will
have the option to inherit this ``package.json`` egg-info metadata.
One way to do this is through that package's ``setup.py``.  By invoking
``setup.py npm --init`` from there, a new ``package.json`` will be
written to the current directory as if running ``npm init`` with all the
dependencies declared through the Python package dependency tree for the
given Python package.

Expose JavaScript code from a Python module
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
        [calmjs.module.pythonic]
        example.package = example.package
        """
        ...
    )

The separator for the namespace and the module will use the ``.``
character instead of ``/``.  However given that the ``.`` character is
a valid name for a JavaScript module, the usage of this is ill-advised,
but it does make JavaScript code look a bit more Pythonic at the cost of
lessened standards compliance with the target language.


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


Contribute
----------

- Issue Tracker: https://github.com/calmjs/calmjs/issues
- Source Code: https://github.com/calmjs/calmjs


License
-------

The ``calmjs`` project is licensed under the GPLv2 or later.

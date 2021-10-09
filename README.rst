calmjs
======

A Python framework for building toolchains and utilities for working
with the Node.js ecosystem from within a Python environment.

.. image:: https://github.com/calmjs/calmjs/actions/workflows/build.yml/badge.svg?branch=3.4.2
    :target: https://github.com/calmjs/calmjs/actions/workflows/build.yml?query=branch:3.4.2
.. image:: https://ci.appveyor.com/api/projects/status/45054tm9cfk7ryam/branch/3.4.2?svg=true
    :target: https://ci.appveyor.com/project/metatoaster/calmjs/branch/3.4.2
.. image:: https://coveralls.io/repos/github/calmjs/calmjs/badge.svg?branch=3.4.2
    :target: https://coveralls.io/github/calmjs/calmjs?branch=3.4.2

.. |AMD| replace:: AMD (Asynchronous Module Definition)
.. |calmjs.bower| replace:: ``calmjs.bower``
.. |calmjs| replace:: ``calmjs``
.. |calmjs_npm| replace:: ``calmjs npm``
.. |calmjs.rjs| replace:: ``calmjs.rjs``
.. |calmjs.webpack| replace:: ``calmjs.webpack``
.. |npm| replace:: ``npm``
.. |r.js| replace:: ``r.js``
.. |setuptools| replace:: ``setuptools``
.. |webpack| replace:: ``webpack``
.. |yarn| replace:: ``yarn``
.. _AMD: https://github.com/amdjs/amdjs-api/blob/master/AMD.md
.. _Bower: https://bower.io/
.. _calmjs.bower: https://pypi.python.org/pypi/calmjs.bower
.. _calmjs.rjs: https://pypi.python.org/pypi/calmjs.rjs
.. _calmjs.webpack: https://pypi.python.org/pypi/calmjs.webpack
.. _Node.js: https://nodejs.org/
.. _npm: https://www.npmjs.com/
.. _r.js: https://github.com/requirejs/r.js
.. _setuptools: https://pypi.python.org/pypi/setuptools
.. _webpack: https://webpack.js.org/
.. _yarn: https://yarnpkg.com/


Introduction
------------

Calmjs defines an extensible framework for interoperability between
Python and `Node.js`_ runtime for Python packages, to provide their
developers a well defined interface for bi-directional access between
Node.js/Javascript development tools and the JavaScript code within
their Python packages, such that a proper, formal integration with
Node.js/JavaScript environment from a Python environment can be
facilitated.  The goal of the Calmjs framework is to aid the
development, testing, and deployment of Python packages that also
include and/or integrate with external JavaScript code.


Methodology
-----------

First, this is achieved by providing Python packages the ability to
declare dependencies on Node.js/JavaScript packages or source files that
are required to complete their functionality.  This common framework
will ensure the accessibility of these metadata under a common protocol,
to avoid incompatible declarations that are not portable between
different projects and environments, or being otherwise scattered across
different tools or locations or be duplicated within the same working
environments by different sets of tools.  Without a common framework,
the result is that Python packages will be unable to properly
communicate their non-Python requirements and states between each other,
resulting in difficulties in building, development and deployment of the
software stack, and/or becoming a source of errors for those processes.

Second, by offering a set of tools built on top of this extensible
framework to work with these declarations for generating the
configuration files for required Node.js tools, so that they can
construct the required the build and/or runtime environment for their
functionality.

Ultimately, this permits better Node.js integration with a given Python
environment, lowering the amount of effort needed to achieve continuous
integration and/or delivery of Python packages in conjunction with
Node.js/JavaScript packages in a reproducible manner.

Implementation
~~~~~~~~~~~~~~

In order to achieve this, the Calmjs framework provides a set of
extension to |setuptools|_ that assists with the tracking and management
of dependencies of JavaScript or Node.js based packages (such as ones
through |npm|_) for a given Python package.  It also provides a number
of base classes that can be used to build custom toolchains that
implement different strategies for managing and compiling required
JavaScript code and related assets into the deployment artifacts that an
application server may use, or to generate test harnesses to ensure
correctness under both the development and production environment.
These extra functionalities will be provided by other Python packages
under the |calmjs| namespace in order to realize this modular
architecture.

The name Calmjs was originally derived from the steps in the first
iteration of the toolchain which involves the steps compile, assemble,
and linkage into a module of JavaScript using the namespace from the
host Python package.  The `m` in the logo is the ear of a rabbit.  The
reason this animal is chosen as the mascot for this project is because
of their dietary habits, as it's analogous to how JavaScript code is
typically turned into a minimally usable level by other tools and
framework.


Features overview
-----------------

A framework for integration with Node.js based package managers
    Through |setuptools| command hooks, |calmjs| provides Python
    packages with the ability to declare and manage manifest definition
    files for Node.js based package management systems (e.g. such as
    ``package.json`` for |npm|).  Under typical usage, this means the
    declaration of ``dependencies`` or ``devDependencies`` for the
    JavaScript packages needed by a given Python package can be tracked,
    all within the |setuptools| framework through the extensions
    provided by |calmjs|.

    The other part of this infrastructure is that these declarations
    follow the Python package dependency graph.  Developers and users
    can make use of the |calmjs| console command entry point, or through
    |setuptools|, to generate a manifest file to facilitate the
    installation of Node.js packages required by the Python packages
    within the completed application stack, tailored for all the
    packages at hand.

    |calmjs| includes the integration support for both |npm|_ and
    |yarn|_ by default.

Export JavaScript code out of Python packages with the same namespace
    A given Python package that included associated JavaScript source
    code within the same Python module and namespace structure alongside
    Python source code within the source tree, will be able to declare
    those namespaces as the root for those JavaScript modules under the
    exact same Python package namespace through |setuptools| entry
    points.

    These declarations will be available through registries exposed by
    the |calmjs| module registry system for other packages to turn those
    declarations through the API provided by the framework into working
    JavaScript code following the same declared module and namespace
    structures.  The default module registry will make use of the ``/``
    character (instead of the ``.`` character like in Python) as the
    separator for the names due to established naming conventions in
    JavaScript (and in ES6 towards the future).

    Other tools that works with the Calmjs framework can then make use
    of these raw JavaScript source files in conjunction with the local
    Node.js environment, or generate artifacts for deployment over the
    web.  This leads to...

Better integration of JavaScript toolchains into Python environments
    This is achieved by providing a framework for building toolchains
    for working with tools written in JavaScript for Node.js/JavaScript
    environments that integrates properly with existing Python packages
    and environments.

    There are no limitations as to how or what can be done with the
    tools or the source files, as this is left as an implementation
    detail.  For an example please refer to the |calmjs.rjs|_ Python
    package, which allows the production of |AMD|_ artifacts from
    JavaScript packages embedded inside Python packages, or
    |calmjs.webpack|_ which integrates with |webpack|_ for the
    production of another commonly used bundled artifact format.

    Generally, toolchains can be built to find and load all Python
    packages (through the |calmjs| registry system) that have any
    JavaScript source files, and those will be extracted, go through the
    appropriate transpilers (if any) in order to build deployable
    artifacts.  Test harnesses can be set up to aid with running of unit
    tests, functional testing and naturally the final integration tests
    needed for a successful deployment.

Well-defined modular architecture to ensure code reuse and extensibility
    The features described so far are built upon a foundation of generic
    classes and modules, so that the support for additional JavaScript
    tools or custom process for handling transpilation can be as simple
    as creating a new module for a couple of classes with additional
    parameters with the relevant |setuptools| entry points.

    In fact, |calmjs| out of the box only ships with just the core
    framework plus the |npm|/|yarn| interfacing part, with the support
    for tools like `Bower`_ or |r.js|_ as completely separate packages
    (as |calmjs.bower|_ and |calmjs.rjs|_ respectively), such that
    projects, environments or sites that do not need the functionality
    those packages provide can simply opt to not have them installed.


Installation
------------

As the goal of |calmjs| is to integrate Node.js and |npm| (or |yarn|)
into a Python environment, they need to be available within the
environment; if they are not installed please follow the installation
steps for `Node.js`_ appropriate for the target operating
system/environment/platform.

To install |calmjs| into a given Python environment, the following
command can be executed to install directly from PyPI:

.. code:: console

    $ pip install calmjs

.. _development installation method:

Alternative installation methods (for developers, advanced users)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Development is still ongoing with |calmjs|, for the latest features and
bug fixes, the development version can be installed through git like so:

.. code:: console

    $ # standard installation mode
    $ pip install git+https://github.com/calmjs/calmjs.git#egg=calmjs
    $ # for an editable installation mode; note the upgrade flag
    $ pip install -U -e git+https://github.com/calmjs/calmjs.git#egg=calmjs

Note that the ``-U`` flag for the editable installation is to ensure
that |setuptools| be upgraded to the latest version to avoid issues
dealing with namespaces for development packages, which is documented in
the next paragraph.

Alternatively, the git repository can be cloned directly and execute
``python setup.py develop`` while inside the root of the source
directory, however if this development installation method is done using
any version of |setuptools| earlier than v31, there will be inconsistent
errors with importing of modules under the |calmjs| namespace.  Various
`symptoms of namespace import failures`_ are documented under the
`troubleshooting`_ section of this document.

Testing the installation
~~~~~~~~~~~~~~~~~~~~~~~~

To ensure that the |calmjs| installation is functioning correctly, the
built-in testsuite can be executed by the following:

.. code:: console

    $ python -m unittest calmjs.tests.make_suite

If there are failures, please file an issue on the issue tracker with
the full traceback, and/or the method of installation.  Please also
remember to include platform specific information, such as Python
version, operating system environments and version, and other related
information related to the issue at hand.


Usage and description of key features
-------------------------------------

When installed to a particular Python environment, the |calmjs|
command-line utility will become available within there.

.. code:: console

    $ calmjs
    usage: calmjs [-h] [-d] [-q] [-v] [-V] <command> ...

    positional arguments:
      <command>
        artifact     helpers for the management of artifacts
        npm          npm support for the calmjs framework
        yarn         yarn support for the calmjs framework

    optional arguments:
      -h, --help     show this help message and exit

    global options:
      -d, --debug    show traceback on error; twice for post_mortem
                     '--debugger' when execution cannot continue
      -q, --quiet    be more quiet
      -v, --verbose  be more verbose
      -V, --version  print version information

As mentioned, |npm| support is built-in so it is always available; to
access its help, simply execute ``calmjs npm -h``, which will then list
the options available for that particular subcommand.  If other
subcommands are available (which will be provided by other |calmjs|
integration packages) they will be listed as a ``<command>`` and their
specific help messages will be accessible in the same manner.

Declare a ``package.json`` for a given Python package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _using package_json:

If a package wish to declare dependencies on packages hosted by |npm|,
it may do something like this in its ``setup.py``:

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
        # ...
        setup_requires=[
            'calmjs',
            # plus other setup_requires ...
        ],
        package_json=package_json,
        # ...
    )

Note that ``setup_requires`` section must specify |calmjs| in order to
enable the ``package_json`` setup keyword for the generation of the
``package.json`` metadata file for the given package whenever ``python
setup.py egg_info`` is executed (directly or indirectly), so that even
if |calmjs| is not already installed into the current Python
environment, it will be acquired from PyPI and be included as part of
the |setuptools| setup process, and without being a direct dependency of
the given package.  The ``package.json`` will be generated if the
provided data is either a valid JSON string or a dictionary without
incompatible data types.  For example:

.. code:: console

    $ python setup.py egg_info
    running egg_info
    writing package_json to example.package.egg-info/package.json
    ...
    $ cat example.package.egg-info/package.json
    {
        "dependencies": {
            "jquery": "~3.0.0",
            "underscore": "~1.8.0"
        }
    }

The key reason for using ``setup_requires`` is to not force a given
package's dependents to have |calmjs| as part of their dependencies, as
typically this is a requirement only for developers but not for
end-users.  This also mean that for developers that want to use |calmjs|
and utilities they must install that separately (i.e. ``pip install
calmjs``), or declare |calmjs| as a development dependency through the
usage of ``extras_require`` flag, for example:

.. code:: python

    setup(
        name='example.package',
        # ...
        setup_requires=[
            'calmjs',
            # ...
        ],
        extras_require={
            'dev': [
                'calmjs',
                # ... plus other development dependencies
            ],
        },
        # ...
    )

Then to fully install the package as an editable package with the
dependencies listed under the ``dev`` extras:

.. code:: console

    $ pip install -e .[dev]
    Obtaining file://example/package
    ...
    Installing collected packages: ..., calmjs, ...
      Running setup.py develop for example.package
    Successfully installed ...

Note that now the |calmjs| package remains installed in the Python
environment, and the utilities they provide may now be used, covered by
the following sections.

Using the ``package.json`` across Python package dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. |integrate_with_calmjs_npm| replace:: integration with ``npm``
    through ``calmjs npm``

With the ``package.json`` file written to the package metadata
directory, utilities such as |calmjs| make make use of it.  One method
to do this is through that package's ``setup.py``.  By invoking
``setup.py npm --init`` from there, a new ``package.json``, combined
with all the ``dependencies`` and ``devDependencies`` declared by the
Python package dependencies of the given package, will be written to the
current directory.  This is akin to running ``npm init``, with the
difference being that the dependencies are also being resolved through
the Python package dependency tree for the given Python package.

Do note that this requires the ``package.json`` creation and handling
capability be available for the given package (refer to previous section
on how to achieve this) and all dependencies must be correctly installed
and be importable from the current Python environment.

Alternatively, the |calmjs_npm| utility may be used.  Invoking ``calmjs
npm --init example.package`` from the command line will achieve the same
thing, anywhere on the file system, provided that both |calmjs| and
``example.package`` are installed and available through the current
Python environment's import system.  For more details and information
about this utility, please refer to the |integrate_with_calmjs_npm|_
section.

Dealing with |npm| dependencies with Python package dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Flat is better than nested.  So all ``dependencies`` (and
``devDependencies``) declared by any upstream Python package will be
automatically inherited by all its downstream packages, but they have
the option to override it with whatever they want through the mechanism
as described above.  They can set a JavaScript or Node.js package to
whatever versions desired, or even simply remove that dependency
completely by setting the version to ``None``.

Whenever an actual ``package.json`` is needed by |calmjs|, the
|calmjs_npm| utility flattens all Node.js dependencies needed by the
Python packages into a single file, which is then passed into the
respective JavaScript package manager for consumption.  This process is
also done when a |calmjs| toolchain or utility make use of these
declared information to to generate the desired artifacts to achieve
whatever desired task at hand.

Of course, if the nested style of packages and dependency in the same
style as |npm| is desired, no one is forced to use this, they are free
to use whatever tools to interpret or make use of whatever data files
and dependencies available, and/or to split their packages up to Python
and JavaScript bits and have them be deployed and hosted on both PyPI
(for ``pip``) and |npm| respectively and then figure out how to bring
them back together in a coherent manner.  Don't ask (or debate with) the
author on how the latter option is better or easier for everyone
(developers, system integrators and end-users) involved.

Declare explicit dependencies on paths inside ``node_modules``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Given that the dependencies on specific versions of packages sourced
from |npm| is explicitly specified, build tools will benefit again from
explicit declarations on files needed from those packages.  Namely, the
compiled packages could be declared in the ``extras_calmjs`` section in
JSON string much like ``package_json``, like so:

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

Since ``node_modules`` is declared to be an ``extras_key``, conflicting
declarations between packages within the environment will be resolved
and merged in the same manner as dependencies conflicts declared in
``package_json``.

Please do note that complete path names must be declared (note that the
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

To declare the JavaScript source files within ``./example/package`` as
JavaScript modules through |calmjs|, an entry point can be declared like
so in the ``setup.py`` file:

.. code:: python

    setup(
        ...
        entry_points="""
        ...
        [calmjs.module]
        example.package = example.package
        """,
        ...
    )

Note that the name of the entry point is not relevant; that entry point
name is ignored, as the intention of the default module registry is to
provide a module name that maps directly to the same import namespace
as the source Python module, but with the ES5 namespace separator
``/``, instead of the ``.`` character as in Python.  If an explicit
mapping is required, a new module registry class may be defined that
uses the provided name as the CommonJS import name from the JavaScript
code.

The default method will expose the two source files with the following
names::

    - 'example/package/ui'
    - 'example/package/widget'

For some projects, it may be undesirable to permit this automated method
to extract all the available JavaScript source files from within the
given Python module.

To get around this, it is possible to declare new module registries
through the Calmjs framework.  Provided that the ``ModuleRegistry``
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
        """,
        ...
    )

Do note that while the names permitted for an entry point name is quite
unrestricted, these registry names should be of a standard dotted
namespace format to ensure maximum tool compatibility, as these can be
specified from the command line through tools that utilizes this system.

Once the registry was declared, simply replace ``calmjs.module`` with
the name of that, along with a ``calmjs_module_registry`` attribute that
declare this ``example.module`` registry is the default registry to use
with this package.

.. code:: python

    setup(
        ...
        calmjs_module_registry=['example.package'],
        entry_points="""
        ...
        [example.module]
        example.package = example.package
        """,
        ...
    )

Within the Calmjs framework, tools can be explicitly specified to
capture modules from any or all module registries registered to the
framework.  One other registry was also defined.  If the entry point was
declared like so:

.. code:: python

    setup(
        ...
        entry_points="""
        ...
        [calmjs.py.module]
        example.package = example.package
        """,
        ...
    )

The separator for the namespace and the module will use the ``.``
character instead of ``/``.  However given that the ``.`` character is a
valid name for a JavaScript module, the usage of this may create issues
with certain JavaScript tools.  While AMD based module systems can
generally handle ``.`` characters in imports without issues, allowing
somewhat more Python-like feel importing using dotted names within the
JavaScript environment, however, this may lead to incompatibilities with
other JavaScript libraries thus the usage of this naming scheme is not
recommended.

By default, another registry with the ``.tests`` suffix is also declared
as a compliment to the previously introduced registries, which packages
can make use of to declare JavaScript test code that accompanies the
respective modules that have been declared.  For example:

.. code:: python

    setup(
        ...
        entry_points="""
        ...
        [calmjs.module]
        example.package = example.package

        [calmjs.module.tests]
        example.package.tests = example.package.tests
        """,
        ...
    )

Much like the first example, this declares ``example.package`` as a
Python namespace module that exports JavaScript code, with the
subsequent declaration section being the module that contains the tests
that accompanies the first.

Make available the accompanied resource files to loaders
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Certain Node.js build tools and frameworks support the concept of
"loaders" for other resource files through the same import/require
system for JavaScript modules.  To provide the most basic support to
ease the effort required by package creators to expose other resource
files to the Node.js tooling import systems, a subsidiary loader
registry may be declared and used in conjunction with a parent module
registry.  To extend on the previous example, if following entry points
are defined:

.. code:: ini

    [calmjs.module]
    example.package = example.package

    [calmjs.module.loader]
    json = json[json]
    text = text[txt,json]

The ``calmjs.module.loader`` registry will reference its parent registry
``calmjs.module`` for the specific modules that have been exposed, so
that it will source all the relevant filenames with the declared file
name extensions to a specific loader by name.  Unlike the base module
registry, the module loader registry will ignore the Python module name
section, while the name (on the left-hand side) is the desired loader,
with the extras (comma-separated tokens enclosed between the ``[]``) are
the file name extensions to be acquired from the package.  Thus with the
previously defined entries for the ``example.package``, the following
``require`` statements should resolve if the target resource files exist
for the package:

.. code:: javascript

    // resolved through "json = ...[json]"
    var manifest_obj = require('json!example/package/manifest.json');
    // resolved through "text = ...[txt,json]"
    var manifest_txt = require('text!example/package/manifest.json');
    var index_txt = require('text!example/package/index.txt');

As the values generated by the registry follow the standard toolchain
spec compile entry grammar, this should satisfy the most basic use cases
and can be included directly as a ``calmjs_module_registry`` for the
package.  However, the actual usage in the provided JavaScript code
conjunction with the actual toolchain packages that integrates/interacts
with with their respective Node.js packages may have interactions that
will require special handling (such as inclusion/exclusion of the
generated segments targeted for the final artifact, or how those sources
are aliased or made available to the system, or whether or not the
registry itself requires manual integration); please consult the
documentation for the specific integration package with regards to this
specific registry type.

One final note: due to the limitations of the Python entry point system,
file name extensions are assumed to be all lower-case.

.. _integrate_with_calmjs_npm:

Integration with |npm| through |calmjs_npm|
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As mentioned, it is possible to make use of the ``package.json``
generation capabilities from outside of |setuptools|.  Users can easily
do the same through the built-in ``calmjs npm`` tool:

.. code:: console

    $ calmjs npm --help
    usage: calmjs npm [-h] [-d] [-q] [-v] [-V] [--view] [--init] [--install]
                      [-i] [-m] [-w] [-E] [-P] [-D]
                      <package> [<package> ...]

    npm support for the calmjs framework

    positional arguments:
      <package>          python packages to be used for the generation of
                         'package.json'

    optional arguments:
      -D, --development  explicitly specify development mode for npm install
      -E, --explicit     explicit mode disables resolution for dependencies;
                         only the specified Python package(s) will be used.
      -h, --help         show this help message and exit
      -i, --interactive  enable interactive prompt; if an action requires an
                         explicit response but none were specified through
                         flags (i.e. overwrite), prompt for response;
                         disabled by default
      -m, --merge        merge generated 'package.json' with the one in
                         current directory; if interactive mode is not
                         enabled, implies overwrite, else the difference will
                         be displayed
      -P, --production   explicitly specify production mode for npm install
      -w, --overwrite    automatically overwrite any file changes to current
                         directory without prompting

Naturally, the same ``--init`` functionality shown above with the
|setuptools| framework is available, however package names can be
supplied for generating the target ``package.json`` file from anywhere
on the filesystem, provided that the Python environment has all the
required packages installed.  For instance, if the Node.js packages for
``example.package`` is to be installed, this can be invoked to view the
``package.json`` that would be generated:

.. code:: console

    $ calmjs -v npm --view example.package
    2016-09-01 16:37:18,398 INFO calmjs.cli generating a flattened
    'package.json' for 'example.package'
    {
        "dependencies": {
            "jquery": "~3.0.0",
            "underscore": "~1.8.0",
        },
        "devDependencies": {},
        "name": "example.package"
    }

If there is an existing ``package.json`` file already in the current
directory, using the ``-i`` flag with ``--init`` or ``--install`` will
show what differences there may be between the generated version and the
existing version, and prompt for an action.

Toolchain
~~~~~~~~~

Documentation on how to extend the Toolchain class to support use cases
is currently incomplete.  This is usually combined together with a
``calmjs.runtime.DriverRuntime`` to hook into the ``calmjs`` runtime.

Unfortunately at this time a detailed guide on how to create a complete
implementation is not completed (only documentation within the class
are, however).  For a working example on how this may be achieved please
refer to the implementations provided by |calmjs.rjs|_ or
|calmjs.webpack|_.

Toolchain Advice
~~~~~~~~~~~~~~~~

For package developers that need to provide additional instructions to
a toolchain execution (e.g. for compatibility between RequireJS and also
webpack for specific use case of features to a given package), the
toolchain system will also make use of the advice system such that
additional instructions may be created and registered for use and reuse
by their dependents.  Much like the Toolchain, this feature is currently
lacking in documentation outside of the test cases.

Pre-defined artifact generation through |setuptools|
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to define the artifacts to be generated for a given
package and the rule to do so.  Simply define a function that return an
instance of a ``calmjs.toolchain.Toolchain`` subclass that have
integrated with the desired tool, and a ``calmjs.toolchain.Spec`` object
with the rules needed.  These specific functions are often provided by
the package that offers them, please refer to the toolchain packages
listed and linked in the previous section for further details on how
these might be used.

As these are also implemented through the registry system, the entry
points generally look like this:

.. code:: python

    setup(
        ...
        build_calmjs_artifacts=True,
        entry_points="""
        ...
        [calmjs.artifacts]
        complete.bundle.js = example.toolchain:builder
        """,
        ...
    )

In the example, the ``builder`` function from the module
``example.toolchain`` is used to generate the ``complete.bundle.js``
file.  The generated artifact files will reside in the
``calmjs_artifacts`` directory within the package metadata directory
(one that ends with either ``.dist-info`` or ``.egg-info``) for that
package.  An accompanied ``calmjs_artifacts.json`` file will also be
generated, listing the versions of the various Python packages that were
involved with construction of that artifact, and the version of binary
that was used for the task.

When the ``build_calmjs_artifacts`` is set to ``True``, the hook for
automatic generation of these artifacts through the ``setup.py build``
step will enabled.  This is useful for automatically bundling the
artifact file with a release such as Python wheels (e.g. running
``setup.py bdist_wheel`` will also build the declared artifacts.
Otherwise, this step can be manually invoked using
``setup.py build_calmjs_artifacts`` or through the
``calmjs artifact build`` tool.


Troubleshooting
---------------

The following may be some issues that may be encountered with typical
usage of |calmjs|.

CRITICAL calmjs.runtime terminating due to a critical error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If |calmjs| encounters any unexpected situation, it may abort like so:

.. code:: console

    $ calmjs npm --install calmjs.dev
    CRITICAL calmjs.runtime terminating due to a critical error

If no useful ERROR message is listed before, please try running again
using a debug flag (either ``-d`` or ``--debug``).

.. code:: console

    $ calmjs -d npm --install calmjs.dev
    CRITICAL calmjs.runtime terminating due to exception
    Traceback (most recent call last):
    ...

Specifying the debug flag twice will enable the ``post_mortem`` mode,
where a debugger will be fired at the point of failure.  Authors of
packages that implement runtime classes that provide subcommands to the
|calmjs| command may find this useful during their development cycles.
Do note that the default debugger is only triggered if the top level
runtime class enable the usage (which the runtime class that implement
the |calmjs| command does) and if the failure occur during the
invocation of the runtime class.  Any other errors or exceptions that
occur during the setup stage of the |calmjs| runtime will simply be
logged at a lower priority level (e.g. to make warnings generated during
the setup stage visible, additional verbose flags must be provided).

ERROR bad 'calmjs.runtime' entry point
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ImportError
    This is typically caused by improper removal of locally installed
    packages that had an entry point registered, an addon package to
    |calmjs| registered entry points pointing to bad import locations,
    or conflicting installation methods was used for the current
    environment as outlined in the installation section of this
    document.  Either reinstall the broken package again with the
    correct installation method for the environment, or fully uninstall
    or remove files belonging to the packages or sources that are
    triggering the undesirable error messages.

bad entry point
    This is caused by packages defining malformed entry point.  The name
    of the package triggering this error will be noted in the log; the
    error may be reported to its developer.

.. _symptoms of namespace import failures:

Random ``ImportError`` when trying to import from the |calmjs| namespace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As |calmjs| is declared as both namespace and package, there are certain
low-level setup that is required on the working Python environment to
ensure that all modules within can be located correctly.  However,
versions of |setuptools| earlier than `v31.0.0`__ does not create the
required package namespace declarations when a package is installed
using a `development installation method`_ (e.g. using ``python setup.py
develop``) into the Python environment in conjunction with another
package that was installed through ``pip`` within the same namespace.
Failures can manifest as inconsistent import failures for any modules
under the |calmjs| namespace.  As an example:

.. __: https://setuptools.readthedocs.io/en/latest/history.html#v31-0-0

.. code:: pycon

    >>> from calmjs import tests
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    ImportError: cannot import name tests
    >>> from calmjs import parse  # calmjs.parse was installed via pip
    >>> from calmjs import tests
    >>> # no failure, but it was failing just earlier?

It could also manifest differently, such as an ``AttributeError``, which
may be triggered through the execution of unittests for |calmjs|:

.. code:: console

    $ coverage run --include=src/* -m unittest calmjs.tests.make_suite
    Traceback (most recent call last):
      ...
        parent, obj = obj, getattr(obj, part)
    AttributeError: 'module' object has no attribute 'tests'
    $ python -m calmjs.tests.make_suite
    /usr/bin/python: No module named 'calmjs.tests'

To resolve this issue, ensure that |setuptools| is upgraded to v31 or
greater, which may be installed/upgraded through ``pip`` like so:

.. code:: console

    $ pip install --upgrade setuptools

Then reinstall all the required packages that are under the |calmjs|
namespace to resolve this import issue.

Environmental variables being ignored/not passed to underlying tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Generally speaking, the Calmjs framework filters out all environmental
variables except for the bare minimum by default, and only passes a
limited number to the underlying tool.  These are the ``PATH`` and the
``NODE_PATH`` variables, plus platform specific variables to enable
execution of scripts and binaries.

Runtime reporting 'unrecognized arguments:' on declared arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This issue should be fully resolved for calmjs>=3.1.0.

The default behavior in the ArgumentParser defaults to uselessly blaming
the root parser for any unrecognized arguments caused by its subparsers.
The original workaround prior to calmjs-3.1.0 had the failure as
documented below as its subparser resolver implementation was
incomplete.  Either of these misleading behaviors impede the end users
from being able to quickly locate the misplaced argument flags.

For instance, if the |calmjs| command was executed like so resulting in
error message may look like this:

.. code:: console

    $ calmjs subcmd1 subcmd2 --flag item
    usage: calmjs subcmd1 ... [--flag FLAG]
    calmjs subcmd1: error: unrecognized arguments: --flag

This means that ``--flag`` is unrecognized by the second subcommand
(i.e. the ``calmjs subcmd1 subcmd2`` command) as that was placed after
``subcmd2``, but the subparser for ``subcmd1`` flagged that as an error.
Unfortunately there are a number of issues in the ``argparse`` module
that makes it difficult to fully resolve this problem, so for the mean
time please ensure the flag is provided at the correct subcommand level
(i.e.  in this case, ``calmjs subcmd1 --flag item subcmd2``), otherwise
consult the help at the correct level by appending ``-h`` to each of the
valid subcommands.

Module registry not locating files from namespace packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are a number of edge cases associated with namespace packages in
Python, especially if they are provided on the system through different
methods (i.e. mix of zipped eggs, wheels and development packages).
While workarounds for handling of namespace modules for the given
packages are provided, there are limitations in place.  One such cause
is due to complexity in dealing with zipped eggs; if this is an issue,
please ensure that the affected package has ``zip_safe`` declared as
false, or alternatively generate a Python wheel then install that wheel,
if the target Python environment has that as the standard installation
format.

UserWarning: Unknown distribution option: 'package_json'
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This also applies to other relevant options, as it is caused by the
execution of ``setup.py`` without |calmjs| being available to
|setuptools|, such that the handling method for these keywords remain
undefined.  This can be corrected by providing |calmjs| as part of the
``setup_requires`` section.  Further information on this may be found in
the `using package_json`_ section of this document.


Contribute
----------

- Issue Tracker: https://github.com/calmjs/calmjs/issues
- Source Code: https://github.com/calmjs/calmjs


Legal
-----

The Calmjs project is copyright (c) 2016 Auckland Bioengineering
Institute, University of Auckland.  |calmjs| is licensed under the terms
of the GPLv2 or later.

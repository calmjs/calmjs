Module layout
=============

A listing of all modules in the ``calmjs`` package; also serves as a
guide on how modules should be laid out for packages that directly
depend on and extend off of ``calmjs``.

As a rule, a module should not inherit from modules listed below
their respective position on the following list.  If inheritance must be
done, it must be done within a local scope to ensure that circular
dependencies do not form.  This rule also extends to the unittest
modules.

exc
    Generic exception classes specific for this project.

utils
    Utilities for use from within calmjs (maybe elsewhere).  Must NOT
    inherit from other calmjs modules.  As a result this is safe to be
    imported from any ``test_`` modules.

interrogate
    Helper functions that make use of ``calmjs.parse`` for interrogating
    JavaScript source files for various information.

vlqsm
    Deprecated module - contains stub import points for VLQ helpers,
    along with a legacy source map generator helper class.

argparse
    Extensions to the built-in ``argparse`` module.  Due to this name,
    ``absolute_import`` must be used.

base
    Module providing Base* classes.  Should only inherit from utils and
    nothing else.

ui
    For functions and classes that provide user interfacing features,
    including constants that are used for rendering output to logs and
    users.  The interactive mode features are typically reserved for
    usage by the runtime module, although often other modules may use
    provide references to functions here as default callbacks.

registry
    Root registry class.  Inherits from base.  Should not inherit from
    anything else.

command
    Provides the primitives for distutils/setuptools integration.  It
    should not inherit from anything but rather the downstream users
    should compose the instances with whatever it needs, with data
    provided by the registry.

indexer
    Contains a microregistry and a number of functions for generation
    of mappings of files within modules in Python packages for the
    purpose of exporting the paths of the JavaScript sources they hold.
    Shouldn't really need expanding or shouldn't need to inherit from
    calmjs.

module
    Defines module related registries, uses the indexer to generate the
    module path mapping entries.

dist
    Module that interfaces with distutils/setuptools in order to provide
    functions for dealing with distributions (i.e. dependencies and
    requirements for packages).  Should not really inherit from
    anything, however it is done for the core registry stuff which
    provides the functions that interfaces with the registry system that
    setuptools provide.

toolchain
    The exported primitive of this project.  Provides the skeleton
    Toolchain class for other packages to extend upon.  While some
    toolchain modules might provide cli interfacing functionalities,
    they should not inherit from cli as this is not the module that will
    provide the user facing entry points.

cli
    Module that provides the functions that call out to cli tools that
    will support the functionality needed by the calmjs framework.
    Provides the expanded driver classes for interfacing with Node.js
    and its tools, and also the primitive exposed functions that provide
    its own shell.  This latter part could be exposed as the runtime
    library.

artifact
    Defines all artifact integration functionalities; includes the
    related registries, makes use of the dist and command modules for
    the resolution of dependencies of packages and hooks into the
    setuptools infrastructure.

runtime
    The module that provides the classes and functions that aid with
    providing the entry point into calmjs from cli and elsewhere.
    Supports the generation of the texts for users from the shell.

npm
    The npm specific tools.  Whole module can in theory be generated
    from code, however without the source users will be lost.  So that's
    done like so for the integrated thing that could inherit from
    anything.

yarn
    Provides the interface to npm package repository but through yarn.

loaderplugin
    While loader plugin handlers of this package can be considered as
    part of the lower level infrastructure (just under toolchain), the
    actual items being encapsulated is actually JavaScript code that
    interfaces with the JavaScript/Node.js ecosystem in a rather tightly
    coupled manner, and that it needs the helpers in the npm module to
    locate the target source files.  Given that, these objects should
    only be accessed through the registry system.  For dependent
    packages, especially packages that implement toolchains, this
    particular constraint will likely be inapplicable and thus it may
    sit lower than their respective toolchain/cli packages.

calmjs
    Provide an alternative execution method of the runtime, which may be
    accessed by running ``python -m calmjs.calmjs``.

Module layout
=============

To give a guide on how modules should be laid out, in the case for other
packages that that may depend on ``calmjs`` for integration and other
uses, the following are how things are done here:

utils
    Utilities for use from within calmjs (maybe elsewhere).  Must NOT
    inherit from other calmjs modules.

base
    Module providing Base* classes.  Should only inherit from utils and
    nothing else.

registry
    Root registry class.  Inherits from base.  Should not inherit from
    anything else.

dist
    Module that interfaces with distutils/setuptools in order to provide
    functions for dealing with distributions (i.e. dependencies and
    requirements for packages).  Should not really inherit from
    anything, however it is done for the core registry stuff which
    provides the functions that interfaces with the registry system that
    setuptools provide.

toolchain
    The exported primative of this project.  Provides the skeleton
    Toolchain class for other packages to extend upon.  While some
    toolchain modules might provide cli interfacing functionalities,
    they should not inherit from cli as this is not the module that will
    provide the user facing entry points.

cli
    Module that provides interface between the cli tools and also to
    provide more cli functionalities that expand on those.  Provides the
    expanded driver classes for interfacing with Node.js and its tools,
    so it might end up inheriting from toolchain also.

command
    Provides the primative package manager command.  While it doesn't
    really inherit from anything here, implementations will likely
    inherit from dist for helpers and cli for the actual cli interfacing
    part for the underlying binary for the command.  This is what the
    cli_driver is for.

indexer
    Constains a microregistry and a number of functions for generation
    of mappings of files within modules in Python packages for theu
    purpose of exporting the paths of the JavaScript sources they hold.
    Shouldn't really need expanding or shouldn't need to inherit from
    calmjs.

module
    Defines module related registries, uses the indexer to generate the
    module path mapping entries.

npm
    The npm specific tools.  Whole module can in theory be generated
    from code, however without the source users will be loss.  So that's
    done like so for the integrated thing that could inherit from
    anything.

As a general rule, modules above should not inherit from modules below.

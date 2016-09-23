Comparison of ``calmjs`` vs. ``bower``
======================================

While the ``calmjs`` framework at a glance appears to be a Python
reimplementation of `Bower`_, it does provide features in a manner more
catered to a Python-centric workflow, and does so through a bit more
formalism.

.. _Bower: https://bower.io

Bower (under typical usage by the programming community, observations
gathered mostly from other Python projects):

- Is its own package management framework, largely for any kind of
  github hosted package.
- Package acquisition for any kind of resources hosted on github or
  other locations.  No restrictions on declaration on source, but once
  the source location is declared it's largely fixed.
- Can extend requirements arbitrarily using any conforming web resources
  (i.e. git repositories on github with a bower.json defined in its
  root).
- Largely leverages github for package hosting.  The tool cannot easily
  generate an installation from a private repository for public packages
  from a private index (without editing configuration).  Changing
  distribution acquisition source necessitates the modification of
  manifest file (``bower.json``).
- Packages acquired typically in its raw form, unless specific plugins
  are invoked to build; no unified system exist for this; no special
  accommodation for specific package formats.
- Not specifically optimized on any package format, thus a generic tool
  but does not offer a standard on how to handle them, but up to
  individual plugins.
- Artifact production can be done through plugins, such as
  ``grunt-bower-requirejs``, which in turn leverages upon grunt.
- No dedicated testing tool or harness generation on artifacts produced.
- No registry system on where code or resources actually are within a
  given package
- Installation not as portable.
- Does not natively provide a way to easily use JavaScript code deployed
  with Python through a common namespace/module structure; will setup
  its own copy in ``bower_components`` under default configuration.

The calmjs framework:

- Not a package manager, but leverages Python's setuptools/pip for its
  package management, and provides tools that interfaces/integrates with
  other package managers written in Node.js or others.
- Package acqusition for Python packages done through pip; other systems
  and/or repositories are supported via plugins (i.e. for npm, bower);
  no native restriction on locations (determined by tool used).
- No arbitrary extension on requirements as calmjs is not a package
  manager (but pip can be leveraged to achieve this, i.e. ``pip -r
  requirements.txt``, or using the built-in merge functionality with a
  local json file, but this informalism result in potential issues).
- While pip leverages PyPI for package hosting by default, calmjs does
  not rely on that - provided wheels are built/hosted, the installation
  environment can rely on private hosts for the acqusition of packages,
  simply by telling pip where the links are with ``--find-links``; can
  use git too for package hosting.
- Packages acquired are built by Python typically, or already pre-built
  as Python wheels; no unified systems for assets/artifact production.
- Optimized for operation on Python packages; Python wheels can contain
  JavaScript code thus all the code required by a project to generate
  all artifacts needed.
- Artifact production can be done through extensions to framework, such
  as ``calmjs.rjs``.
- Ability to generate tests for JavaScript code through ``calmjs.dev``
  (to be written)
- Dedicated testing tool and harness generation on both development and
  artifacts with tests associated with packages required.
- Defines a registry system to register locations on what sources are
  exported by packages; external (to Python) dependencies can be
  declared explicitly by packages down to the files they need.
- Portable installation.
- Provides a way to export JavaScript code in a Python package with a
  common namespace/module structure.

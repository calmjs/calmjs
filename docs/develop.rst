Development guidelines for calmjs
=================================

This document covers the basic development procedures surrounding the
``calmjs`` and related project.

Using calmjs for working with JavaScript
----------------------------------------

Please refer to the user/usage documentations found in ``usage.rst``.

Extending calmjs
----------------

Please refer to the developer documentations found in ``extend.rst``.

Contribution guidelines
-----------------------

Bug fixes to ``calmjs`` and other forms of contributions that align with
the goals of the project are welcomed, however there are standards that
must be adhered to in order to maintain the quality of the project.

To keep things simple, and to maintain maximum code quality standards,
please adhere to the following:

- Full test coverage on master at all times; this includes 100% coverage
  on the tests themselves (helps with picking out test methods that have
  name clashes within a TestCase class).
- Code without tests, or code being omitted from testing must have
  explanation in associated commit message (with exception of continue
  statements that got marked as missing due to this `coverage
  <https://bitbucket.org/ned/coveragepy/issues/198/>`_ and `CPython
  issue <http://bugs.python.org/issue2506>`_).
- Development should be done on branches or forks, to allow squashing of
  trivial commits to not influence the master branch.
- Feature branches, when completed, should be rebased on the relevant
  branches.  If the feature is minor and relevant to a fix that changes
  no semantic meaning to the release it is targeting, it should be
  rebased on the earliest release branch it is applicable for.  Merges
  from there up towards the latest release will then occur to preserve
  the commit identifiers for the feature that was implemented.
- Tests must be passing on master.  Yes this includes ``flake8``.
- Commit messages MUST adhere to the 50/72 format, especially for prose
  where the requirements for this is strictly followed.
- Commits will be rejected if they do not follow the above standards, or
  at best be edited to follow suite before accepted into master.

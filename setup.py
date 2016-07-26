from setuptools import setup, find_packages
import sys, os

version = '0.0'

setup(name='calmjs',
      version=version,
      description="Toolchain for deploying JavaScript with Python modules.",
      long_description=open('README.rst').read(),
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Tommy Yu',
      author_email='tommy.yu@auckland.ac.nz',
      url='https://github.com/calmjs/',
      license='GPL',
      packages=find_packages('src', exclude=['ez_setup']),
      package_dir={'': 'src'},
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools>=11.3',
      ],
      entry_points="""
      # -*- Entry points: -*-
      [distutils.commands]
      npm = calmjs.command:npm

      [distutils.setup_keywords]
      package_json = calmjs.dist:validate_package_json

      [egg_info.writers]
      package.json = calmjs.dist:write_package_json
      """,
      test_suite="calmjs.tests.test_suite",
      )

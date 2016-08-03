from setuptools import setup
from setuptools import find_packages

version = '0.0'

classifiers = """\
Development Status :: 4 - Beta
Environment :: Console
Framework :: Setuptools Plugin
Intended Audience :: Developers
License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)
Operating System :: OS Independent
Programming Language :: JavaScript
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3.3
Programming Language :: Python :: 3.4
Programming Language :: Python :: 3.5
""".splitlines()

setup(name='calmjs',
      version=version,
      description="Toolchain for deploying JavaScript with Python modules.",
      long_description=open('README.rst').read(),
      classifiers=classifiers,
      keywords='',
      author='Tommy Yu',
      author_email='tommy.yu@auckland.ac.nz',
      url='https://github.com/calmjs/',
      license='GPL',
      packages=find_packages('src', exclude=['ez_setup']),
      package_dir={'': 'src'},
      namespace_packages=['calmjs'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools>=11.3',
      ],
      python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*',
      entry_points="""
      # -*- Entry points: -*-
      [distutils.commands]
      npm = calmjs.npm:npm

      [distutils.setup_keywords]
      package_json = calmjs.dist:validate_json_field

      [egg_info.writers]
      package.json = calmjs.npm:write_package_json
      """,
      test_suite="calmjs.tests.test_suite",
      )

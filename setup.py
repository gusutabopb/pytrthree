#!/usr/bin/env python
import sys
from setuptools import setup
from setuptools.command.install import install

if sys.version_info.major != 3:
    sys.exit('Support Python 3 only')


class Installer(install):
    pass


with open('README.md', 'r') as f:
    long_description = f.read()

setup(name='pytrthree',
      version='0.1.0',
      description='A Pythonic wrapper for the TRTH API based on Zeep.',
      long_description=long_description,
      author='Gustavo Bezerra',
      author_email='gusutabopb@gmail.com',
      url='https://github.com/plugaai/pytrthree',
      packages=['pytrthree'],
      license='GPL',
      install_requires=['zeep', 'pytest'],
      classifiers=[
          'Intended Audience :: Developers',
          'Intended Audience :: Science/Research',
          'Intended Audience :: Financial and Insurance Industry',
          'Development Status :: 3 - Alpha',
          'Programming Language :: Python :: 3.6'
          "Topic :: Software Development :: Libraries",
      ])

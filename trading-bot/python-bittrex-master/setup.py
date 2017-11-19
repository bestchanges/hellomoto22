#!/usr/bin/env python

from distutils.core import setup


setup(name='python-bittrex',
      version='0.2.0',
      packages=['bittrex'],
      modules=['bittrex'],
      description='Python bindings for bittrex API.',
      author='Eric Somdahl',
      author_email='eric@corsairconsulting.com',
      classifiers=[
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.6',
          'Operating System :: OS Independent',
          'License :: OSI Approved :: MIT License',
          'Development Status :: 3 - Alpha',
          'Topic :: Office/Business :: Financial',
      ])

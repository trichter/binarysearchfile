# (C) 2024, Tom Eulenfeld, MIT license

from setuptools import setup


def read_readme_without_badges():
    with open('README.md') as f:
        return '\n'.join(line for line in f.read().splitlines()
                         if not line.startswith('[!['))


setup(long_description=read_readme_without_badges(),
      long_description_content_type='text/markdown')

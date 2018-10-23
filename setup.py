import pathlib
from setuptools import setup


readme = pathlib.Path(__file__).parent / 'README.rst'
with readme.open() as readme_data:
    long_description = readme_data.read()


setup(
    name='agnostic',
    version='1.1.0-dev', # Update docs/conf.py also!
    author='Mark E. Haase',
    author_email='mehaase@gmail.com',
    description='Agnostic Database Migrations',
    long_description=long_description,
    license='MIT',
    keywords='database migrations',
    url='https://github.com/TeamHG-Memex/agnostic',
    packages=['agnostic'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Utilities',
    ],
    # Keep the dependencies in sync with tests/docker/Dockerfile dependencies:
    install_requires=[
        'Click>=7.0,<8.0',
        'sqlparse>=0.2.4,<0.3.0',
    ],
    extras_require = {
        'mysql': ['PyMySQL>=0.9.2,<0.10.0'],
        'postgres': ['pg8000>=1.12.3,<1.13.0'],
        'sqlite3': [], # No actual dependencies, only here for symmetry.
    },
    entry_points='''
        [console_scripts]
        agnostic=agnostic.cli:main
    '''
)

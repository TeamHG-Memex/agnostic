from setuptools import setup


setup(
    name='agnostic',
    version='0.11', # Update docs/conf.py also!
    author='Mark E. Haase',
    author_email='mehaase@gmail.com',
    description='Agnostic Database Migrations',
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
    install_requires=[
        'Click>=7.0,<8.0',
        'sqlparse>=0.2.4,<0.3.0',
    ],
    extras_require = {
        'dev': ['nose>=1.3.7,<1.4.0'],
        'mysql': ['PyMySQL>=0.9.2,<0.10.0'],
        'postgres': ['pg8000>=1.12.3,<1.13.0'],
    },
    entry_points='''
        [console_scripts]
        agnostic=agnostic.cli:main
    '''
)

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
        'Click',
        'sqlparse',
    ],
    extras_require = {
        'mysql': ['PyMySQL'],
        'postgres': ['pg8000'],
    },
    entry_points='''
        [console_scripts]
        agnostic=agnostic.cli:main
    '''
)

from setuptools import setup


setup(
    name='agnostic',
    version='0.6',
    author='Mark E. Haase',
    author_email='mehaase@gmail.com',
    description='Agnostic Database Migrations',
    license='MIT',
    keywords='database migrations',
    url='https://github.com/TeamHG-Memex/agnostic',
    py_modules=['agnostic'],
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
    ],
    entry_points='''
        [console_scripts]
        agnostic=agnostic:cli
    '''
)

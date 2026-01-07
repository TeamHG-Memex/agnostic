Installation
============

Install From PyPI
-----------------

The easiest way to install Agnostic is from PyPI.

.. note::

    Agnostic requires Python 3, so make sure that you are using ``pip3``, not
    ``pip2``. Don't worry: you can use Agnostic with Python 2 projects — or
    projects written in *any programming language* — but Agnostic itself needs
    to run in the Python 3 interpreter.

Agnostic requires a specific driver for each database you want to use it with,
**so choose one of the following forms to install Agnostic with the correct
drivers.**

.. code:: bash

    ~ $ pip3 install agnostic[mysql]
    ~ $ pip3 install agnostic[postgres]
    ~ $ pip3 install agnostic[sqlite]

Agnostic expects some database tools to be present in order to make snapshots
and backups. You only need to install dependencies for the database that you're
using.

mysql
    Requires the ``PyMySQL`` Python driver and both the ``mysql`` and
    ``mysqldump`` executables.

postgres
    Requires the ``pg8000`` Python driver and both the ``psql`` and
    ``pg_dump`` executables.

sqlite3
    Requires the ``sqlite3`` executable.


Install From Source
-------------------

Agnostic is also easy to install from source, in case you want to install a pre-
release version. You can clone the repo or download a Zip file from `the
project's repository <https://github.com/TeamHG- Memex/agnostic>`_. Once you
have it cloned or unzipped, run the ``setup.py`` script.

.. note::

    Make sure to use Python 3, not Python 2. See notice in previous section.

Go into the Agnostic directory **and then install using one of the following
forms.**

.. code:: bash

    ~ $ cd agnostic
    ~/agnostic $ pip3 install .[mysql]
    ~/agnostic $ pip3 install .[postgres]
    ~/agnostic $ pip3 install .[sqlite]

Make sure to review the dependencies in the "Install from PyPI" section above.

Verification
------------

You can verify that Agnostic is installed by running the following command.
(Your version number may not match the version shown here. That's OK.)

.. code:: bash

    ~ $ agnostic --version
    agnostic, version 1.0

This command does not check your dependencies, so you may still find that
Agnostic does not work when you start trying to interact with your database. In
that case, review the dependency information in the previous sections again.

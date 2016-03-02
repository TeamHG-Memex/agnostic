Installation
============

Install From PyPI
-----------------

The easiest way to install Agnostic is from PyPI.

.. note::

    Agnostic is Python 3 only, so make sure that you are using ``pip3``, not
    ``pip2``. Don't worry: you can use Agnostic with Python 2 projects; only
    Agnostic itself needs to run in the Python 3 interpreter.

.. code:: bash

    ~ $ pip install agnostic

Install From Source
-------------------

Agnostic is also easy to install from source, in case you want to install a pre-
release version. `Clone it from Github <https://github.com/TeamHG-
Memex/agnostic>`_ or `download a ZIP file <https://github.com/TeamHG-
Memex/agnostic/archive/master.zip>`_. Once you have it cloned or unzipped, just
run the ``setup.py``.

.. note::

    Make sure to use Python 3, not Python 2. See notice in previous section.

.. code:: bash

    ~ $ cd agnostic
    ~/agnostic $ python setup.py install

Dependencies
----------------

Agnostic expects some database drivers and tools to be present in order to
connect to and execute queries against your database.

postgres
    Requires the ``psycopg2`` Python driver and both the ``psql`` and
    ``pg_dump`` executables.

*In this alpha release, "postgres" is the only supported database.*

Testing
-------

You can test if Agnostic is installed correctly by running it.

.. code:: bash

    ~ $ agnostic --version
    agnostic, version 1.0

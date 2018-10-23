Agnostic Database Migrations
============================

.. image:: https://img.shields.io/pypi/v/agnostic.svg?style=flat-square
   :target: https://pypi.python.org/pypi/agnostic
   :alt: PyPI Version

.. image:: https://img.shields.io/travis/TeamHG-Memex/agnostic.svg?style=flat-square
    :target: https://travis-ci.org/TeamHG-Memex/agnostic
    :alt: Build Status

.. image:: https://img.shields.io/coveralls/github/TeamHG-Memex/agnostic.svg?style=flat-square
    :target: https://coveralls.io/github/TeamHG-Memex/agnostic?branch=master
    :alt: Code Coverage

Overview
--------

Agnostic is a light-weight, easy-to-learn, and flexible database migration tool
in which migration scripts are written in pure SQL. It is agnostic towards
database, programming language, and object relational mapper (ORM).

Super Quick Start
-----------------

Here is an absurdly brief introduction to Agnostic:

.. code:: bash

    ~/myapp $ mkdir migrations

    ~/myapp $ agnostic -t postgres -u myuser -d mydb bootstrap
    Migration table created.

    ~/myapp $ cat > migrations/add_cell_phone.sql
    ALTER TABLE customer ADD cell_phone VARCHAR(255);
    ^D

    ~/myapp $ cat > migrations/add_nickname.sql
    ALTER TABLE customer ADD nickname VARCHAR(255);
    ^D

    ~/myapp $ agnostic -t postgres -u myuser -d mydb migrate
    Backing up "mydb" to "/tmp/tmpm8glpgaa".
    About to run 2 migrations in "mydb":
     * Running migration add_cell_phone (1/2)
     * Running migration add_nickname (2/2)
    Migrations completed successfully.
    Removing backup "/tmp/tmpm8glpgaa".

For a not-quite-as-quick-but-still-pretty-quick start, please refer to the
`full documentation <https://agnostic.readthedocs.io//>`_.

----

.. image:: https://hyperiongray.s3.amazonaws.com/define-hg.svg
	:target: https://www.hyperiongray.com/?pk_campaign=github&pk_kwd=agnostic
	:alt: define hyperiongray

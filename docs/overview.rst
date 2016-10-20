Overview
========

Agnostic Database Migrations is a database migration tool that is agnostic to:

* database system
* programming language
* object/relational mapper (ORMs)
* schema build system
* merging source code branches
* workflow

Favoring convention over configuration, Agnostic is lightweight and conceptually
simple.

**Stop stressing about migrations and start using Agnostic!**

Quick Start
-----------

Ok, Mr. or Mrs. Impatient, you don't want to read 14 pages of dry, technical
documentation. You just want to see what it can do, right?

We'll assume that you already have a running application that uses a schema
named ``myapp``. This application has a single table called ``customer``:

.. code:: sql

    CREATE TABLE customer (
        name character varying(255),
        address character varying(255),
        home_phone character varying(255)
    );

.. note::

    One of the beautiful features of Agnostic is that doesn't care how you got
    to this point, or what tools you use to build your database. You can build
    your schema with a SQL script, an ORM, or even the butterfly effect.
    Agnostic won't get jealous.

Now your customers are demanding a few features, and these new features require changes to the existing schema:

1. Add a ``cell_phone`` column.
2. Add a ``nickname`` column.

**Let's see how we can do this with Agnostic.**

**First, create a directory to hold the migrations.** We will name the directory
``migrations``. (You could name it something else, but that would take a few
extra minutes to explain, and that wouldn't make for a "quick" start would it?)

.. code:: bash

    ~/myapp $ mkdir migrations

**Next, bootstrap the migrations system.** This step creates a table inside your
database to hold metadata about migrations.

.. code:: bash

    ~/myapp $ agnostic -t postgres -u myuser -d mydb bootstrap
    Migration table created.

**Now, write SQL scripts for each of the changes** and save them in the
``migrations`` folder.

.. code:: bash

    ~/myapp $ cat > migrations/add_nickname.sql
    ALTER TABLE customer ADD nickname VARCHR(255);

    ~/myapp $ cat > migrations/add_cell_phone.sql
    ALTER TABLE customer ADD cell_phone VARCHAR(255);

**Finally, run the migrations:**

.. code:: bash

    ~/myapp $ agnostic -t postgres -u myuser -d mydb migrate
    Backing up schema "myapp" to "/tmp/tmprhty1nc7".
    About to run 2 migrations in schema "myapp":
     * Running migration add_cell_phone (1/2)
     * Running migration add_nickname (2/2)
    Migration failed because:
    failed to run external tool "psql" (exit 3):
    ERROR:  type "varchr" does not exist
    LINE 1: ALTER TABLE customer ADD nickname VARCHR(255);
                                              ^

    Will try to restore from backup…
    Restored from backup.
    Aborted!

**Ruh roh!** The first migration ran fine, but it looks like the second migration
has a typo: ``VARCHR`` instead of ``VARCHAR``.

Luckily, Agnostic automatically backs up your database before running
migrations. In the event of a failure, it automatically restores from that
backup so that you don't get stuck in an in-between state.

.. note::

    When working with a database that supports transactional DDL, you can
    disable Agnostic's automatic backup/restore behavior with the
    ``--no-backup`` flag.

Let's fix the typo and run it again.

.. code:: bash

    ~/myapp $ sed -i 's:VARCHR:VARCHAR:' migrations/add_nickname.sql
    ALTER TABLE customer ADD nickname VARCHAR(255);

    ~/myapp $ agnostic -t postgres -u myuser -d mydb migrate
    Backing up schema "myapp" to "/tmp/tmpm8glpgaa".
    About to run 2 migrations in schema "myapp":
     * Running migration add_cell_phone (1/2)
     * Running migration add_nickname (2/2)
    Migrations completed successfully.
    Removing backup "/tmp/tmpm8glpgaa".

**Sweet! You're done…**

Agnostic keeps track of what migrations have already been applied, so we can
easily run future migrations without accidentally re-executing previous
migrations.

.. code:: bash

    ~/myapp $ cat > migrations/drop_nickname.sql
    ALTER TABLE customer DROP nickname;

    ~/myapp $ agnostic -t postgres -u myuser -d mydb list
    Name           | Status    | Started At          | Completed At
    ---------------+-----------+---------------------+--------------------
    add_cell_phone | succeeded | 2015-05-23 21:09:33 | 2015-05-23 21:09:34
    add_nickname   | succeeded | 2015-05-23 21:09:34 | 2015-05-23 21:09:34
    drop_nickname  | pending   | N/A                 | N/A

    ~/myapp $ agnostic -t postgres -u myuser -d mydb migrate
    Backing up schema "myapp" to "/tmp/tmpiq5fhnh6".
    About to run 1 migration in schema "myapp":
     * Running migration drop_nickname (1/1)
    Migrations completed successfully.
    Removing backup "/tmp/tmpiq5fhnh6".

**Easy peasy, right?**

Purpose
-------

If you're new to migrations, or coming from a different migrations system, you
may be wondering what exactly is meant by "agnostic database migrations".

When you develop and deploy an application that is backed up by a relational
database, you will eventually need to deploy a new version of that application
that expects a slightly different, improved schema. In most production use
cases, it's not acceptable to just drop the database and rebuild it. Instead,
you must modify the existing database to match what the application expects, and
you need to do so without corrupting or destroying any of your production data.

On small projects, you might be able to handle this process manually: you write
a SQL script for each new release and then you run that script whenever you need
to deploy an upgraded version.

On large projects, however, you'll find that it quickly grows to be a bigger
problem that you can reasonably manage. It becomes very difficult to ensure that
all of your environments have exactly the same schema; the bugs that arise from
having slightly different schemas in different places (imagine a missing foreign
key constraint) cause corrupted data to build up slowly over time and eventually
turn into a nightmarish debugging scenario.

Alternatives
------------

There are a lot of options for database migrations:

* Django (Python) has `South <https://south.readthedocs.org/en/latest/>`_.
* Doctrine (PHP) has `Migrations <http://www.doctrine-project.org/projects/migrations.html>`_.
* Java has `migrate4j <http://migrate4j.sourceforge.net/>`_.
* Perl has `DBIx::Migration::Directories <http://search.cpan.org/~crakrjack/DBIx-Migration-Directories-0.12/lib/DBIx/Migration/Directories.pod>`_.
* PHP has `Phinx <https://phinx.org/>`_.
* Ruby On Rails has `Active Record Migrations <http://edgeguides.rubyonrails.org/active_record_migrations.html>`_
* SQLAlchemy (Python) has `Alembic <https://alembic.readthedocs.org/en/latest/>`_.

(This is just a sample of the many tools out there.)

*Why are there so many different migration tools?*

The main reason that there are so many tools is that — for some strange reason —
the developers think that each programming language and/or ORM needs its own
separate migration tool. These solutions are simultaneously over-engineered and
too restrictive.

Consider the `Alembic tutorial
<https://alembic.readthedocs.org/en/latest/tutorial.html>`_ as an example:

1. Run ``alembic init`` to intialize a directory structure, including an
   ``env.py`` configuration file.
2. You *also* need an ``alembic.ini`` file, which contains 20 configuration
   directives by default.
3. Edit a Mako template file in order to customize automatically generated
   migrations. *(You have free time to learn Mako, right?)*
4. Run ``alembic revision -m foo`` to create a template for a new migration
   script.
5. Write the migration script in Python, using the Alembic API. *(You have time
   to learn that API, right?)*
6. Write an ``upgrade()`` method for the migration, and you may write a
   ``downgrade()`` method as well. *(Just keep in mind that downgrading won't
   work at all if you have even a single migration that doesn't implement
   downgrade().)*

As if you didn't have already have enough complex things to learn, memorize, and
operate, these migration systems expect you read 100 pages of documentation just
so you can manage migrations. Hopefully you're not thinking about using a
different ORM or programming language on your next project — you'll have to
learn a whole new migrations system, too!

**In contrast, consider Agnostic:**

* Lightweight.
* Migrations written in pure SQL.
* No configuration files.
* Don't have to generate scaffolding.
* Simple enough to completely understand how it works.
* Flexible enough to fit a lot of different workflows.
* Not tied to a specific programming lanuage.
* Not tied to a specific ORM.
* Not tied to a specific database.
* High automated test coverage.
* Open source.

Agnostic is the last migrations system you'll ever learn.

License
-------

Agnostic is released under an `MIT license <https://github.com/TeamHG-
Memex/agnostic/blob/master/LICENSE>`_.

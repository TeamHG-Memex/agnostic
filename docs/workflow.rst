.. _workflow:

Workflow
========

Overview
--------

Agnostic doesn't impose any particular workflow—that's one of its selling
points! This document describes a hypothetical workflow for the purpose of
illustration. By stepping through this workflow, we may gain a better insight
into how to use Agnostic within any workflow of our choosing.

In this hypothetical scenario, we are going to be developing a customer
database. Along the way, we will use Agnostic's testing tools to make sure that
our migrations work the way we expect them to. We will also handle a merge from
a coworker's source code.

.. note::

    We'll be using PostgreSQL throughout this example workflow. If you're using
    a different system, then you may need to adjust some of the SQL statements,
    but the concepts should translate readily.

Initial Set Up
--------------

To begin with, let's assume we've never used Agnostic on this project before. We
need to create a directory to hold our migration scripts and then bootstrap the
migrations system.

.. code:: bash

    ~/myapp $ mkdir migrations

    ~/myapp $ agnostic -t postgres -u myuser -d mydb bootstrap
    Migration table created

That's it! If you're familiar with other migrations systems, then you may be
wondering where the rest of the set up procedure is.

Snapshot Current Database Structure
-----------------------------------

In our hypothetical application, we are using an ORM. We define our data models
using the ORM API and then the ORM generates SQL to build a database structure.

.. note::

    This ORM build process saves us effort, as long as we can make sure that
    building a new database structure from scratch always produces the same
    exact result as running migrations on an existing database structure.

Our ORM outputs SQL to create a customer table like this:

.. code:: sql

    CREATE TABLE customer (
        name VARCHAR(255) PRIMARY KEY,
        address VARCHAR(255),
        phone VARCHAR(255)
    );

Before we begin working on a new task, we should snapshot the current database
structure. A snapshot contains database structure statements, but it does not
include any data. Snapshots are useful for testing, which we will see later.

.. code:: bash

    ~/myapp $ agnostic -t postgres -u myuser -d mydb snapshot current.sql
    Creating snapshot...
    Snapshot written to "current.sql".

We name the file ``current.sql`` so that we can compare later database builds to
it.

Build New Database With ORM
---------------------------

We put Agnostic aside for a while and tinker with our ORM data models. After
some time building and testing our new features, we ask the ORM to build a new
database.

.. code:: sql

    CREATE TABLE customer (
        name VARCHAR(255) PRIMARY KEY,
        address VARCHAR(255),
        home_phone VARCHAR(255),
        cell_phone VARCHAR(255)
    );

This example may be small enough that the database changes are obvious, but real
world use cases will often be far more complex. Let's use Agnostic to help us
understand what the ORM has changed. We'll begin by taking a second snapshot.

.. code:: bash

    ~/myapp $ agnostic -t postgres -u myuser -d mydb bootstrap
    Migration table created

    ~/myapp $ agnostic -t postgres -u myuser -d mydb snapshot target.sql
    Creating snapshot...
    Snapshot written to "target.sql".

Now we have two SQL files, ``current.sql`` and ``target.sql``. The former
describes how our database structure looked before we started working on these
new features, and the latter describes the target state that we want our
migrations to produce.

Let's compare these two database structures to identify the differences.

.. code:: bash

    ~/myapp $ diff current.sql target.sql
    51c51,52
    <     phone character varying(255)
    ---
    >     home_phone character varying(255),
    >     cell_phone character varying(255)

The diff helps us see that the ``phone`` column was replaced with ``home_phone``
and ``cell_phone``. Now that we have some idea what we need to do, we can write
some migrations that convert the database structure in ``current.sql`` into the
database structure in ``target.sql``.

.. _test-migrations:

Write & Test Migrations
-----------------------

We could write one migration to change both phone number fields, but for the
purpose of highlighting Agnostic's features, we'll write these as two separate
migrations.

.. code:: bash

    ~/myapp $ cat > migrations/add_home_phone.sql
    ALTER TABLE "customer" RENAME COLUMN "phone" to "home_phone";

    ~/myapp $ cat > migrations/add_cell_phone.sql
    ALTER TABLE "customer" ADD COLUMN "cell_phone" VARCHAR(255);

With most migration systems, we'd simply cross our fingers, check in these
scripts, and hope that they produce the precise effect that we desire. However,
we'd really like to test that these migrations produce exactly the same database
structure that the ORM generated.

Here's a possible testing process:

1. Load a "current" snapshot of the database.
2. Run migrations on the current snapshot.
3. Snapshot this new, migrated database.
4. Build a new database using your ORM.
5. Snapshot this ORM-built database.
6. Compare the migrated snapshot to the target snapshot.
7. If there are any differences between the snapshots, then the test fails.
8. If the snapshots are identical, then the test passes and we can go to lunch
   early!

Sounds like a lot of thankless, tedious work, right?

**Luckily, Agnostic automates this process!**

.. code:: bash

    ~/myapp $ agnostic -t postgres -u myuser -d mydb test current.sql target.sql
    WARNING: This will drop the database "myapp"!
    Are you 100% positive that you want to do this? [y/N]: y
    Dropping database "myapp".
    Loading current snapshot "current.sql".
    About to run 2 migrations in database "myapp":
     * Running migration add_cell_phone (1/2)
     * Running migration add_home_phone (2/2)
    Finished migrations.
    Snapshotting the migrated database.
    Comparing migrated database to target database.
    Test passed: migrated database matches target database!

In just a few seconds, Agnostic was able to perform that tedious testing process
that we were dreading, and better yet, it proves that our migrations do exactly
what we hoped for!

You can now commit your migrations with a high degree of assurance. (If you are
actually heading out to lunch right now, can you get me a sandwich? I'm
famished. Thanks!)

Merge Coworker's Branch
-----------------------

Of course, you always write perfect code on the first try, don't you, dear
reader? But what happens when you merge in your coworkers' code? You can easily
test that their migrations work correctly and are compatible with your own
migrations.

.. code:: bash

    ~/myapp $ # SCM checkout original version && ORM build database

    ~/myapp $ agnostic -t postgres -u myuser -d mydb bootstrap
    Migration table created

    ~/myapp $ agnostic -t postgres -u myuser -d mydb snapshot current.sql
    Creating snapshot...
    Snapshot written to "current.sql".

    ~/myapp $ # SCM checkout latest version && ORM build database

    ~/myapp $ agnostic -t postgres -u myuser -d mydb bootstrap
    Migration table created

    ~/myapp $ agnostic -t postgres -u myuser -d mydb snapshot target.sql
    Creating snapshot...
    Snapshot written to "target.sql".

    ~/myapp $ agnostic -t postgres -u myuser -d mydb test current.sql target.sql
    WARNING: This will drop the database "myapp"!
    Are you 100% positive that you want to do this? [y/N]: y
    Dropping database "myapp".
    Loading current snapshot "current.sql".
    About to run 3 migrations in database "myapp":
     * Running migration add_cell_phone (1/3)
     * Running migration add_home_phone (2/3)
     * Running migration add_office_phone (3/3)
    Error: failed to run external tool "psql" (exit 3):
    ERROR:  column "phone" does not exist

Shnikeys! Your coworker's ``add_office_phone`` migration didn't work. What could
have gone wrong? Let's take a look at coworker's migration.

.. code:: bash

    ~/myapp $ cat migrations/add_office_phone.sql
    ALTER TABLE "customer" RENAME COLUMN "phone" to "office_phone";

Recall that Agnostic sorts migrations alphabetically, so your migration
``add_home_phone`` renames the ``phone`` column before your coworker's migration
script has a chance to run.

Fortunately, Agnostic made it easy to catch this mistake, so let's try fixing it:

.. code:: bash

    ~/myapp $ cat > migrations/add_office_phone.sql
    ALTER TABLE "customer" ADD COLUMN "office_phon" VARCHAR(255);

Now re-execute the test:

.. code:: bash

    ~/myapp $ agnostic -t postgres -u myuser -d mydb test current.sql target.sql
    WARNING: This will drop the database "myapp"!
    Are you 100% positive that you want to do this? [y/N]: y
    Dropping database "myapp".
    Loading current snapshot "current.sql".
    About to run 3 migrations in database "myapp":
     * Running migration add_cell_phone (1/3)
     * Running migration add_home_phone (2/3)
     * Running migration add_office_phone (3/3)
    Finished migrations.
    Snapshotting the migrated database.
    Comparing migrated database to target database.
    Test failed: migrated database differs from target database.

    --- Migrated DB
    +++ Target DB
    @@ -50,7 +50,7 @@
         address character varying(255),
         home_phone character varying(255),
         cell_phone character varying(255),
    -    office_phon character varying(255)
    +    office_phone character varying(255)
     );

    Error: Test failed. See diff output above.

This time, the migration runs successfully, but it doesn't produce the correct
database structure. Agnostic points out where the migrated database differs from
the target database, and the mistake is blindingly obvious: you misspelled
"phone" in your migration!

One last fix and re-test:

.. code:: bash

    ~/myapp $ sed -i 's:office_phon:office_phone:' migrations/add_office_phone.sql

    ~/myapp $ agnostic -t postgres -u myuser -d mydb test current.sql target.sql
    WARNING: This will drop the database "myapp"!
    Are you 100% positive that you want to do this? [y/N]: y
    Dropping database "myapp".
    Loading current snapshot "current.sql".
    About to run 3 migrations in database "myapp":
     * Running migration add_cell_phone (1/2)
     * Running migration add_home_phone (2/2)
     * Running migration add_office_phone (3/3)
    Finished migrations.
    Snapshotting the migrated database.
    Comparing migrated database to target database.
    Test passed: migrated database matches target database!

Nice work, sir or madam! You've earned an 80's style movie slow clap.

Clap… Clap… Clap… Clap…

.. note::

    Because migration testing is so easy, you can easily retest multiple times
    at various stages in your team's software development lifecycle. In
    particular, you should consider running one last test before each release
    that covers all of the migrations in that release. This helps catch merge
    issues.

Migrate Production
------------------

When you've done your due dilligence during development, there's not much left
to be surprised by when you migrate your production databases.

.. code:: bash

    ~/myapp $ agnostic -t postgres -u myuser -d mydb migrate
    Backing up database "myapp" to "/tmp/tmpuy2v7hxc".
    About to run 3 migrations in database "myapp":
     * Running migration add_cell_phone (1/3)
     * Running migration add_home_phone (2/3)
     * Running migration add_office_phone (3/3)
    Migrations completed successfully.
    Removing backup "/tmp/tmpuy2v7hxc".

Smooth as pie, easy as silk. (Is that a thing people say?)

.. note::

    Agnostic is a well-behaved command line script so that it is easy to
    integrate in your deployment or upgrade scripts. Once you get comfortable
    with it, migrations can just be another step in your lights-out build/deploy
    process.

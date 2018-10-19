Design
======

Overview
--------

The best way to understand Agnostic is to learn how it works under the hood and
the reasoning that supports its design. Both of these aspects are very simple —
I promise! The conceptual simplicity of Agnostic is one of its strong points.

Before we begin, we need to define a few terms that are occasionally overloaded
by database vendors.

.. note::

    We define `schema <https://en.wikipedia.org/wiki/Database_schema>`_ to mean
    the logical structure of your data, e.g. the tables, types, and constraints,
    written in a `data definition language
    <https://en.wikipedia.org/wiki/Data_definition_language>`_. It's the thing
    that Agnostic manages for you.

    Some database products [unfortunately] define *schema* to be a logical
    grouping of database objects. We avoid such usage of the word in this
    documentation, but the command line interface does use the ``-s/--schema``
    argument in this sense.

    We define the term *database* to refer to the product, server daemon
    process, and/or highest level container for all database objects. Although
    this definition is broad, it is consistent with most vendors' terminology.

Now, let's quickly review the essential elements of Agnostic's design…

Pure SQL
--------

In order to truly be agnostic, as well as reduce learning curve, Agnostic
migration scripts are always written in pure SQL. You won't need to learn a new
API just to write migration scripts, and you also won't be confined by the
capabilities of that API.

Some migrations systems can convert migrations written in their native API to
pure SQL for DBAs that insist on seeing real SQL. However, like most
machine-generated code, this transliterated SQL tends to be overly complex and difficult to read. By writing migrations in SQL from the start, you can write
them to be human-readable.

Data vs. Schema
---------------

Some migration systems offer to help manage data for you. Others focus
exclusively on managing the schema only.

Agnostic *focuses* on managing the schema, but that does not prohibit managing
data. The "pure SQL" aspect of writing migrations means that you can of course
write DML statements to manipulate data.

Agnostic provides tools for verifying the correctness of schema modifications
(see :ref:`test_migrations`), but due to the innumerable complexities of real
world data, it does not attempt to verify correctness of data modifications.

Up vs. Down
-----------

Some migration systems allow you write both "up" scripts (upgrade the schema)
and "down" scripts (revert the schema to an earlier version).

In Agnostic, there is no concept of a "down" migration, for the following
reasons:

1. Allowing two scripts for each migration complicates the storage and metadata
   for migration scripts.
2. If an "up" migration discards some data, such as dropping a table, then there
   is no possible way to write a "down" migration that restores that data.
3. Despite being nominally optional, "down" scripts only work if *all
   migrations* have "down" scripts. If even a single migration lacks a "down"
   script, then there is no possibility for downgrading.
4. The need for downgrading a schema in production is very rare; for those use
   cases where it is valuable, a backup may be faster, easier, and safer.

There are many limitations and caveats on "down" scripts, and in years of
development work, this author has decided that the costs far outweight any
benefits.

Storing Migrations
------------------

Migration scripts are stored in files contained within a directory of your
choosing. By convention, this directory is called ``migrations`` and agnostic
will look for it in your current working directory, but you can choose any
directory and pass it to agnostic with the ``-m/--migrations-dir`` argument.

There is no prescribed layout for files within this folder; you are free to
arrange your migration scripts however you want. All you need to know are these
two rules:

    1. Migrations are named according to their relative path within the
       migration directory, without the ``.sql`` suffix.
    2. Migrations are sorted by name.

These rules are illustrated by the following example. Assume that you have the
following directory tree.

.. code::

    migrations/
        add_phone_column.sql
        drop_last_name_index.sql
        social/
            add_friends_join_table.sql
            add_favorites_column.sql
        readme.txt
        zero_balance_constraint.sql

Agnostic will scan this directory and enumerate the following migration names:

.. code::

    add_phone_column
    drop_last_name_index
    social/add_friends_join_table
    social/add_favorites_column
    zero_balance_constraint

Each migration has been named by taking its path (relative to the ``migrations``
directory) and removing the ``.sql`` suffix. Files without a ``.sql`` suffix are
ignored. The names are sorted (case insensitive) so that they will always be
applied in a deterministic order.

.. danger::

    The first rule of Agnostic migrations is:

        **You do not talk about Agnostic migrations!**

    No wait, hold up… that's the first rule of *Fight Club*. Sorry, I was
    getting really hyped up. The first rule of migrations is actually much
    tamer, but no less important:

        **Do not rename migrations after you have deployed them!**

    Migration names are used to keep track of which migrations have been applied
    and which have not been applied. (That process is described further down.)
    If you rename a migration, it will likely lead to that migration being
    applied twice, which could result in a migration failure.

    In a development environment, you'll probably be fine renaming migrations,
    as long as you and other developers know how to rebuild a schema from
    scratch. But in a production environment, it's just asking for trouble.

Sample File Layout
------------------

You may now be wondering:

    *How does Agnostic manage dependencies between migrations?*

What a good looking question, fair reader!

Some migrations systems ignore this question altogether, and other systems
tackle this question by introducing complex dependency resolution — yet another
cognitive load for developers who want migrations that "just work".

**Agnostic's simple and open-ended approach allows you to manage dependencies
however you like, but without introducing a lot of extra work.**

Here is an example file layout for migrations that minimizes dependency
management without adding significant cognitive load. This is just an example,
of course! You may find similar systems that work even better for you own team,
and Agnostic is cool with that.

Let's assume that you use `semantic versioning <http://semver.org/>`_ or
something like it. We will group all migrations into subdirectories, where each
subdirectory has a 6 digit name that corresponds to a semantic version number.
For example, version 1.2.3 would be named ``010203`` and version 12.34.56 would
be named ``123456``.

This convention gives us a migrations directory layout like this:

.. code::

    migrations/
        010000/
            add_address_line_2.sql
            add_home_phone.sql
        010001/
            add_cell_phone.sql
        010200/
            normalize_phones.sql
        020000/
            add_user_join_table.sql

.. note::

    You can nest directories as deeply as you want, in case you want more fine-
    grained finer subgroups.

The beauty of this simple arrangement is that Agnostic will automatically sort
migrations into the correct order: scripts for version 1.0.1 run before scripts
for version 1.2.0, which in turn run before scripts for version 2.0.0. Any
dependency conflicts between versions are automatically handled for us, with
hardly any extra work on our own part.

But what about dependency conflicts within a single version? Again, Agnostic
doesn't prescribe a single, right answer. You have a lot of options, and it's
best for your team to pick a convention that works for you and stick to it. Here
are some ideas:

1. If conflicts are related to the same feature, that might be a good hint that
   they belong in the same migration script. Try combining them into a single
   SQL script where the statements are re-ordered to solve the dependency.
2. Re-order the migrations by prefixing the file names with special characters.
   An exclamation (``!``) sorts to the top, while an at-symbol (``@``) sorts to
   the bottom.
3. If you have dozens or hundreds of migration scripts per version, then the
   special character approach may get cumbersome. Try moving the scripts that
   have dependency conflicts on each other into a subdirectory together, and
   then use special characters to reorder them within that subdirectory.

.. _metadata:

Metadata
--------

Migration metadata is stored in the same schema that Agnostic is managing for
you. This arrangement is highly convenient: Agnostic already has access to this
schema, and the metadata stays right next to your data. If you backup your
database, then your Agnostic metadata is backed up, too!

The metadata table looks like this:

.. code:: sql

    CREATE TABLE "agnostic_migrations" (
        name VARCHAR(255) PRIMARY KEY,
        status VARCHAR(255),
        started_at TIMESTAMP,
        completed_at TIMESTAMP
    )

We saw in a previous section how the migration name is determined (relative path, minus the ``.sql`` suffix). The status can be any of the following:

* **bootstrapped:** The migration was added to the table when the migration
  system was bootstrapped, but it was never actually executed.
* **succeeded:** The migration was successfully executed.
* **failed:** The migration failed.
* **pending:** The migration has not been executed yet, but would be executed if
  you ran the ``migrate`` command.

For a more thorough explanation of *bootstrapped*, see: :ref:`build_vs_migrate`.

The ``started_at`` and ``completed_at`` columns make for a simple audit history,
so that you can see when various migrations were actually applied to a
particular system.

.. _running_migrations:

Running Migrations
------------------

Now that we know how migration files are stored on disk and how migrations are
represented in a table, we can complete the puzzle: running migrations. This is a rough outline of how migrations are executed.

1. **Make a backup, if requested.**
2. Compute pending migrations
    a. Enumerate all migration files in the migrations directory and sort them
       as described previously.
    b. Enumerate all the migrations that exist in the metadata table.
    c. The "pending" migrations are those that exist on disk but not in the
       metadata table.
3. For each pending migration:
    a. Enter the migration into the metadata table, set the status to
       ``failed``, and set the ``started_at`` time to the current time.
    b. Try to run the pending migration.
    c. If it succeeds, change the status to ``succeeded`` and set the
       ``completed_at`` time to the current time.
    d. If it fails, abort the entire process. If a backup was requested in step
       1, try to restore from that backup now.
4. **If all migrations completed successfully and a backup file was created in
   step 1, then remove that backup file.**

Note that Agnostic fails fast: an error in any single migration causes the
entire process to be aborted. In order to make this process as painless as
possible, Agnostic backs up the schema before it attempts to migrate it. This
backup is automatically restored in the event of a failure.

.. note::

    If restoring from backup fails, please note that the backup file will not
    removed. It remains on disk so that you can attempt a manual recovery.

Some database systems have transactional DDL that allows Agnostic to roll back
all of the migrations in the event of a failure. Agnostic does not, however,
rely on this feature by default, for two reasons:

1. Not all DDL statements are transactional. We don't want you to think you have
   a transactional DDL safety net only to find that it's not there at that one,
   heart-thumping moment when you're migrating a major production database and
   it fails.
2. The overhead of creating a backup is negligible for small and medium sized
   datasets — no more than a few seconds.

If you are confident that you don't need this feature, and you wish to avoid the
overhead of creating a backup file, you may pass the ``--no-backup`` option to
Agnostic.

.. _build_vs_migrate:

Build vs. Migrate
-----------------

Most migration systems are part of an ORM, and most ORMs have an option to
define the schema using a native API, then generate SQL statements to build that
schema. This naturally leads to a difficult question:

    *How do we ensure that the build process always results in the same exact
    schema as migrating?*

This is deceptively difficult. Small difference in schemas across multiple
instances of your application can lead to obvious, catastrophic failure or —
even worse — can lead to the ticking time bomb of slow-but-unnoticed data
corruption. This problem can reach nightmarish magnitudes if you have software
deployed on hundreds or thousands of customer sites.

**It's imperative that all deployed instances of your application have exactly
the same schema.**

Despite the obvious need, it's not clear how best to pursue this stated goal.
One possibility is to ignore your ORM's schema builder and always build new
instances solely from migrations. With this convention, your initial schema is
treated as a "migration #1", and (along with a deterministic migration sort
order) ensures that all instances will always be built identically.

This approach does have drawbacks, though:

1. Your ORM's schema builder is part of the benefit of using an ORM! You are
   creating additional work and also run the risk that the migration script you
   write doesn't perfectly match what the ORM expects.
2. It feels inefficient to have to build a *brand new schema* by building a
   series of old, crufty schemas first.

The other approach is to try to maintain your ORM schema and migrations in
parallel, hoping, praying, and tediously testing to make sure that migration
scripts perfectly replicate the effect of changing your ORM models.

**Agnostic doesn't have an opinionated stance on this question.**

You are free to pick either approach, but if you decide to maintain your ORM
schema and migrations in parallel, then Agnostic can make this process easier
and safer.

When you first bootstrap Agnostic on a given schema, it loads all of the
existing migrations and sets their statuses to ``boostrapped`` — but it doesn't
actually execute any of them. This special status indicates that these are
migrations that already exist in the current schema, but instead of being put
there by running migration scripts, they were put their by the ORM's schema
build tool.

When Agnostic sees this status, it will know that it does not need to run these
migration scripts again. (For more information on how to do this, see:
:ref:`test_migrations`) Once you get used to Agnostic, you may even want to
include the bootstrap step in your schema build process.

On the other hand, if you want to build all new instances from scratch purely
using migrations, then you don't want existing migrations to be bootstrapped,
because that would prevent any of them from running at all! You can disable this
behavior by passing the ``--no-load-existing`` option to the ``bootstrap``
command.

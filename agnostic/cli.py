from contextlib import contextmanager
from datetime import datetime
import difflib
import os
import tempfile

import click
import sqlparse

from agnostic import create_backend, Migration, MigrationStatus


class Config(object):
    ''' Keeps track of configuration. '''

    def __init__(self):
        self.backend = None
        self.debug = False
        self.migrations_dir = None


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option(
    '-t', '--db-type',
    envvar='AGNOSTIC_TYPE',
    metavar='<db_type>',
    required=True,
    type=click.Choice(['mysql', 'postgres']),
    help='Type of database.'
)
@click.option(
    '-h', '--host',
    default='localhost',
    envvar='AGNOSTIC_HOST',
    metavar='<host>',
    required=True,
    help='Database hostname. (default: localhost)'
)
@click.option(
    '-p', '--port',
    type=int,
    envvar='AGNOSTIC_PORT',
    metavar='<port>',
    help='Database port #. If omitted, a default port will be selected based'
         ' on <type>.'
)
@click.option(
    '-u', '--user',
    envvar='AGNOSTIC_USER',
    metavar='<user>',
    required=True,
    help='Database username.'
)
@click.option(
    '--password',
    envvar='AGNOSTIC_PASSWORD',
    metavar='<pass>',
    required=True,
    prompt='Database password',
    hide_input=True,
    help='Database password. If omitted, the password must be entered on stdin.'
)
@click.option(
    '-d', '--database',
    envvar='AGNOSTIC_DATABASE',
    metavar='<database>',
    required=True,
    help='Name of database to target.'
)
@click.option(
    '-s', '--schema',
    envvar='AGNOSTIC_SCHEMA',
    metavar='<schema>',
    required=False,
    help='The default schema[s] to use when connecting to the database.'
         ' (WARNING: EXPERIMENTAL!!!)'
)
@click.option(
    '-m', '--migrations-dir',
    default='migrations',
    envvar='AGNOSTIC_MIGRATIONS_DIR',
    metavar='<dir>',
    required=True,
    type=click.Path(exists=True),
    help='Path to migrations directory. (default: ./migrations)'
)
@click.option(
    '-D', '--debug',
    is_flag=True,
    help='Display stack traces when exceptions occur.'
)
@click.version_option()
@pass_config
def main(config, db_type, host, port, user, password, database, schema,
         migrations_dir, debug):
    ''' Agnostic database migrations: upgrade schemas, save your sanity. '''

    config.debug = debug
    config.migrations_dir = migrations_dir

    try:
        config.backend = create_backend(db_type, host, port, user, password,
                                        database, schema)
    except RuntimeError as re:
        raise click.ClickException(str(re))


@click.command()
@click.option(
    '--load-existing/--no-load-existing',
    default=True,
    help='Track existing migrations in the new migration table. '
         ' (default: --load-existing)'
)
@pass_config
def bootstrap(config, load_existing):
    '''
    Bootstrap the migrations table.

    Agnostic stores migration metadata inside of the database that it is
    managing. The bootstrap process creates a table to store this tracking data
    and also (optionally) loads pre-existing migration metadata into it.
    '''

    with _get_db_cursor(config) as (db, cursor):
        try:
            config.backend.create_migrations_table(cursor)
        except Exception as e:
            if config.debug:
                raise
            msg = 'Failed to create migration table: {}'
            raise click.ClickException(msg.format(e))

        if load_existing:
            for migration in _list_migration_files(config.migrations_dir):
                try:
                    config.backend.bootstrap_migration(cursor, migration)
                except Exception as e:
                    if config.debug:
                        raise
                    msg = 'Failed to load existing migrations: '
                    raise click.ClickException(msg + str(e)) from e

    click.secho('Migration table created.', fg='green')


@click.command()
@click.option(
    '-y', '--yes',
    is_flag=True,
    help='Do not display warning: assume "yes".'
)
@pass_config
def drop(config, yes):
    '''
    Drop the migrations table.

    BACK UP YOUR DATA BEFORE USING THIS COMMAND!

    This destroys all metadata about what migrations have and have not been
    applied. This is typically only useful when debugging.
    '''

    with _get_db_cursor(config) as (db, cursor):
        warning = (
            'WARNING: This will drop all migrations metadata in {}!'
            .format(config.backend.location)
        )

        click.echo(click.style(warning, fg='red'))
        confirmation = 'Are you 100% positive that you want to do this?'

        if not (yes or click.confirm(confirmation)):
            raise click.Abort()

        try:
            config.backend.drop_migrations_table(cursor)
        except Exception as e:
            if config.debug:
                raise
            msg = 'Failed to drop migration table: '
            raise click.ClickException(msg + str(e)) from e

    click.secho('Migration table dropped.', fg='green')


@click.command('list')
@pass_config
def list_(config):
    '''
    List migrations.

    This shows migration metadata: migrations that have been applied (and the
    result of that application) and migrations that are pending.

        * bootstrapped: a migration that was inserted during the bootstrap
          process.
        * failed: the migration did not apply cleanly; the migrations system
          will not be able to operate until this is rectified, typically by
          restoring from a backup.
        * pending: the migration has not been applied yet.
        * succeeded: the migration applied cleanly.

    Applied migrations are ordered by the "started_at" timestamp. Pending
    migrations follow applied migrations and are sorted in the same order that
    they would be applied.
    '''

    with _get_db_cursor(config) as (db, cursor):
        try:
            applied, pending = _get_all_migrations(config, cursor)
            migrations = applied + pending

            if len(migrations) == 0:
                raise click.ClickException('No migrations exist.')

            column_names = 'Name', 'Status', 'Started At', 'Completed At'
            max_name = max([len(m.name) for m in migrations])
            max_status = max([len(m.status.name) for m in migrations])
            row_format = '{{:<{}}} | {{:{}}} | {{:<19}} | {{:<19}}'
            name_col_width = max(max_name, len(column_names[1]))
            status_col_width = max(max_status, len(column_names[2]))
            row = row_format.format(name_col_width, status_col_width)
            date_format = '%Y-%m-%d %H:%I:%S'

            click.echo(row.format(*column_names))
            click.echo(
                '-' * (name_col_width + 1) + '+' +
                '-' * (status_col_width + 2) + '+' +
                '-' * 21 + '+' +
                '-' * 20
            )

            for migration in migrations:
                if migration.started_at is None:
                    started_at = 'N/A'
                else:
                    started_at = migration.started_at.strftime(date_format)

                if migration.completed_at is None:
                    completed_at = 'N/A'
                elif isinstance(migration.completed_at, datetime):
                    completed_at = migration.completed_at.strftime(date_format)

                msg = row.format(
                    migration.name,
                    migration.status.name,
                    started_at,
                    completed_at
                )

                if migration.status == MigrationStatus.bootstrapped:
                    click.echo(msg)
                elif migration.status == MigrationStatus.failed:
                    click.secho(msg, fg='red')
                elif migration.status == MigrationStatus.pending:
                    click.echo(msg)
                elif migration.status == MigrationStatus.succeeded:
                    click.secho(msg, fg='green')
                else:
                    msg = 'Invalid migration status: "{}".'
                    raise ValueError(msg.format(migration.status.name))

        except Exception as e:
            if config.debug:
                raise
            msg = 'Cannot list migrations: {}'
            raise click.ClickException(msg.format(e))


@click.command()
@click.option(
    '--backup/--no-backup',
    default=True,
    help='Automatically backup the database before running ' \
         'migrations, and in the event of a failure, automatically ' \
         'restore from that backup. (default: --backup).'
)
@pass_config
def migrate(config, backup):
    ''' Run pending migrations. '''

    # Get a list of pending migrations.
    with _get_db_cursor(config) as (db, cursor):
        try:
            failed_migrations = config.backend.has_failed_migrations(cursor)
        except Exception as e:
            msg = 'Unable to start migrations: {}'
            raise click.ClickException(msg.format(e))

        if failed_migrations:
            msg = 'Cannot run due to previously failed migrations.'
            raise click.ClickException(click.style(msg, fg='red'))

        _, pending = _get_all_migrations(config, cursor)
        total = len(pending)

        if total == 0:
            raise click.ClickException(
                click.style('There are no pending migrations.', fg='red')
            )

    # Make a backup file [optional].
    if backup:
        backup_file = tempfile.NamedTemporaryFile('w', delete=False)
        msg = 'Backing up {} to "{}".'
        click.echo(msg.format(config.backend.location, backup_file.name))
        _wait_for(config.backend.backup_db(backup_file))
        backup_file.close()

    # Run migrations.
    with _get_db_cursor(config) as (db, cursor):
        msg = 'About to run {} migration{} in {}:'
        click.echo(
            msg.format(total, 's' if total > 1 else '', config.backend.location)
        )

        try:
            _run_migrations(config, cursor, pending)
        except Exception as e:
            click.secho('Migration failed because:', fg='red')
            click.echo(str(e))

            if backup:
                click.secho('Will try to restore from backup…', fg='red')
                config.backend.clear_db(cursor)
                db.close()

                try:
                    with open(backup_file.name, 'r') as backup_handle:
                        _wait_for(config.backend.restore_db(backup_handle))
                    click.secho('Restored from backup.', fg='green')
                except Exception as e2:
                    raise e2
                    msg = 'Could not restore from backup: {}'.format(e2)
                    click.secho(msg, fg='red', bold=True)

            if config.debug:
                raise

            raise click.Abort()

        click.secho('Migrations completed successfully.', fg='green')

    # Remove backup file.
    if backup:
        click.echo('Removing backup "{}".'.format(backup_file.name))
        os.unlink(backup_file.name)


@click.command()
@click.argument('outfile', type=click.File('w'))
@pass_config
def snapshot(config, outfile):
    '''
    Take a snapshot of the current schema and write it to OUTFILE.

    Snapshots are used for testing that migrations will produce a schema that
    exactly matches the schema produced by your build system. See the
    online documentation for more details on how to use this feature.
    '''

    click.echo('Creating snapshot of {}…'.format(config.backend.location))

    try:
        _wait_for(config.backend.snapshot_db(outfile))
        _migration_insert_sql(config, outfile)
    except Exception as e:
        raise click.ClickException('Not able to create snapshot: {}'.format(e))

    click.secho('Snapshot written to "{}".'.format(outfile.name), fg='green')


@click.command()
@click.option(
    '-y', '--yes',
    is_flag=True,
    help='Do not display warning: assume "yes".'
)
@click.argument('current', type=click.File('r'))
@click.argument('target', type=click.File('r'))
@pass_config
def test(config, yes, current, target):
    '''
    Test pending migrations.

    Given two snapshots, one of your "current" state and one of your "target"
    state, this command verifies: current + migrations = target.

    If you have a schema build system, this command is useful for verifying that
    your new migrations will produce the exact same schema as the build system.

    Note: you may find it useful to set up a database for testing separate from
    the one that you use for development; this allows you to test repeatedly
    without disrupting your development work.
    '''

    # Create a temporary file for holding the migrated schema.
    temp_snapshot = tempfile.TemporaryFile('w+')

    # Make sure the user understands what is about to happen.
    warning = (
        'WARNING: This will drop all objects in {}!'
        .format(config.backend.location)
    )

    click.echo(click.style(warning, fg='red'))
    confirmation = 'Are you 100% positive that you want to do this?'

    if not (yes or click.confirm(confirmation)):
        raise click.Abort()

    with _get_db_cursor(config) as (db, cursor):
        # Load the current schema.
        click.echo('Dropping {}.'.format(config.backend.location))
        config.backend.clear_db(cursor)

    click.echo('Loading current snapshot "{}".'.format(current.name))
    _wait_for(config.backend.restore_db(current))

    with _get_db_cursor(config) as (db, cursor):
        # Run migrations on current schema.
        _, pending = _get_all_migrations(config, cursor)
        total = len(pending)
        click.echo(
            'About to run {} migration{} in {}:'
            .format(total, 's' if total > 1 else '', config.backend.location)
        )

        try:
            _run_migrations(config, cursor, pending)
        except Exception as e:
            click.secho('Migration failed because:', fg='red')
            click.echo(str(e))
            raise click.Abort()

        click.echo('Finished migrations.')

    # Dump the migrated schema to the temp file.
    click.echo('Snapshotting the migrated database.')
    _wait_for(config.backend.snapshot_db(temp_snapshot))
    _migration_insert_sql(config, temp_snapshot)

    # Compare the migrated schema to the target schema.
    click.echo('Comparing migrated schema to target schema.')
    temp_snapshot.seek(0)

    ignore = 'INSERT INTO agnostic_migrations'
    migrated = [line for line in temp_snapshot if not line.startswith(ignore)]
    targeted = [line for line in target if not line.startswith(ignore)]

    diff = list(difflib.unified_diff(
        migrated,
        targeted,
        fromfile='Migrated Schema',
        tofile='Target Schema'
    ))

    if len(diff) == 0:
        click.secho(
            'Test passed: migrated schema matches target schema!',
            fg='green'
        )
    else:
        click.secho(
            'Test failed: migrated schema differs from target schema.\n',
            fg='red'
        )
        click.echo(''.join(diff))
        raise click.ClickException('Test failed. See diff output above.')


main.add_command(bootstrap)
main.add_command(drop)
main.add_command(snapshot)
main.add_command(list_)
main.add_command(test)
main.add_command(migrate)


@contextmanager
def _get_db_cursor(config):
    ''' Return a database handle and cursor. '''

    try:
        db = config.backend.connect_db()
    except Exception as e:
        if config.debug:
            raise
        msg = 'Cannot connect to database: {}'
        raise click.ClickException(msg.format(e))

    cursor = db.cursor()

    try:
        config.backend.set_schema(cursor)
    except Exception as e:
        if config.debug:
            raise
        msg = 'Cannot set schema: {}'
        raise click.ClickException(msg.format(e))

    try:
        yield db, cursor
    finally:
        try:
            db.close()
        except:
            pass


def _get_all_migrations(config, cursor):
    '''
    A generator that returns all applied and pending migrations.

    Applied migrations are returned in the order that they were applied.

    Pending migrations are determined by listing all migrations present in
    the migrations directory and removing any migrations that have not been
    applied. They are returned in the order that they should be applied when
    running migrations.
    '''

    applied = config.backend.get_migration_records(cursor)
    applied_set = {migration.name for migration in applied}
    pending = list()

    for migration_name in _list_migration_files(config.migrations_dir):
        if migration_name not in applied_set:
            pending.append(Migration(migration_name, MigrationStatus.pending))

    return applied, pending


def _list_migration_files(migrations_dir, sub_path=''):
    '''
    List all of the migration files in the specified directory by name.

    The name of each migration file is its path relative to ``migrations_dir``
    with the '.sql' suffix removed. The returned list is sorted in alphabetical
    order.
    '''

    migration_prefix_len = len(migrations_dir) + 1
    current_dir = os.path.join(migrations_dir, sub_path)

    for dir_entry in sorted(os.listdir(current_dir), key=str.upper):
        dir_entry_path = os.path.join(current_dir, dir_entry)

        if os.path.isfile(dir_entry_path) and dir_entry.endswith('.sql'):
            yield dir_entry_path[migration_prefix_len:-4]
        elif os.path.isdir(dir_entry_path):
            new_sub_path = os.path.join(sub_path, dir_entry)
            yield from _list_migration_files(migrations_dir, new_sub_path)


def _migration_insert_sql(config, outfile):
    ''' Write SQL for inserting migration metadata to `outfile`. '''

    with _get_db_cursor(config) as (db, cursor):
        insert_sql = (
            "INSERT INTO agnostic_migrations VALUES "
            "('{}', '{}', NOW(), NOW());\n"
        )

        for migration in config.backend.get_migration_records(cursor):
            args = migration.name, MigrationStatus.succeeded.name
            outfile.write(insert_sql.format(*args))


def _run_migrations(config, cursor, migrations):
    ''' Run the specified migrations in the given order. '''

    total = len(migrations)

    def mig2file(migration):
        return os.path.join(
            config.migrations_dir,
            '{}.sql'.format(migration.name)
        )

    for index, migration in enumerate(migrations):
        msg = ' * Running migration {} ({}/{})'
        msg_args = click.style(migration.name, bold=True), index + 1, total
        click.echo(msg.format(*msg_args))

        config.backend.migration_started(cursor, migration)

        with open(mig2file(migration), 'r') as migration_file:
            _run_sql(cursor, migration_file.read())

        config.backend.migration_succeeded(cursor, migration)


def _run_sql(cursor, sql):
    '''
    Run a block of SQL on the specified cursor.

    This breaks up the block into individual statements so that database
    drivers that don't support query stacking (multiple queries at once)
    won't break.
    '''

    for statement in sqlparse.parse(sql):
        if statement.get_type() != 'UNKNOWN':
            cursor.execute(str(statement))


def _wait_for(process):
    ''' Wait for ``process`` to finish and check the exit code. '''

    process.wait()

    if process.returncode != 0:
        msg = 'failed to run external tool "{}" (exit {}):\n{}'

        params = (
            process.args[0],
            process.returncode,
            process.stderr.read().decode('utf8')
        )

        raise click.ClickException(msg.format(*params))


if __name__ == '__main__':
    main()

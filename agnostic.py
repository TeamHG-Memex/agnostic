from copy import copy
from datetime import datetime
import difflib
import importlib
from io import StringIO
import os
import subprocess
import tempfile
from urllib.parse import urlparse

import click


DEFAULT_PORTS = {
    'postgres': 5432,
}

MIGRATION_STATUS_BOOTSTRAPPED = "bootstrapped"
MIGRATION_STATUS_PENDING = "pending"
MIGRATION_STATUS_SUCCEEDED = "succeeded"
MIGRATION_STATUS_FAILED = "failed"


class Config(object):
    ''' Keeps track of configuration. '''

    def __init__(self):
        self.db = None
        self.debug = False
        self.host = None
        self.migrations_dir = None
        self.password = None
        self.port = None
        self.schema = None
        self.type = None
        self.user = None


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option('-t', '--type',
              envvar='AGNOSTIC_TYPE',
              metavar='<type>',
              required=True,
              type=click.Choice(['postgres']),
              help='Type of database.')
@click.option('-h', '--host',
              default='localhost',
              envvar='AGNOSTIC_HOST',
              metavar='<host>',
              required=True,
              help='Database hostname. (default: localhost)')
@click.option('-p', '--port',
              type=int,
              envvar='AGNOSTIC_PORT',
              metavar='<port>',
              help='Database port #. If omitted, a default port will be ' \
                   'selected based on <type>.')
@click.option('-u', '--user',
              envvar='AGNOSTIC_USER',
              metavar='<user>',
              required=True,
              help='Database username.')
@click.option('--password',
              envvar='AGNOSTIC_PASSWORD',
              metavar='<pass>',
              required=True,
              prompt='Database password',
              hide_input=True,
              help='Database password. If omitted, the password must be ' \
                   'entered on stdin.')
@click.option('-s', '--schema',
              envvar='AGNOSTIC_SCHEMA',
              metavar='<schema>',
              required=True,
              help='Name of database schema.')
@click.option('-m', '--migrations-dir',
              default='migrations',
              envvar='AGNOSTIC_MIGRATIONS_DIR',
              metavar='<dir>',
              required=True,
              type=click.Path(exists=True),
              help='Path to migrations directory. (default: ./migrations)')
@click.option('-d', '--debug',
              is_flag=True,
              help='Display stack traces when exceptions occur.')
@click.version_option()
@pass_config
def cli(config, type, host, port, user, password, schema,
        migrations_dir, debug):
    '''
    Agnostic database migrations: upgrade schemas, keep your sanity.
    '''

    config.debug = debug
    config.host = host
    config.password = password
    config.schema = schema
    config.type = type
    config.user = user
    config.migrations_dir = migrations_dir

    if port is None:
        config.port = _get_default_port(config.type)

@click.command()
@click.option('--load-existing/--no-load-existing',
              default=True,
              help='Track existing migrations in the new migration table. ' \
                   ' (default: --load-existing)')
@pass_config
def bootstrap(config, load_existing):
    '''
    Bootstrap the migrations table.

    Agnostic stores migration metadata inside of the database that it is
    managing. The bootstrap process creates a table to store this tracking data
    and also (optionally) loads pre-existing migration metadata into it.
    '''

    db = _connect_db(config)
    cursor = db.cursor()

    try:
        create_table_sql = _get_create_table_sql(config.type)
        cursor.execute(create_table_sql)
    except Exception as e:
        if config.debug:
            raise
        msg = 'Failed to create migration table: %s'
        raise click.ClickException(msg % str(e)) from e

    if load_existing:
        for migration in _list_migration_files(config.migrations_dir):
            try:
                _bootstrap_migration(config.type, cursor, migration)
            except Exception as e:
                if config.debug:
                    raise
                msg = 'Failed to load existing migrations: '
                raise click.ClickException(msg + str(e)) from e

    db.commit()
    click.secho('Migration table created.', fg='green')


@click.command()
@click.option('-y', '--yes',
              is_flag=True,
              help='Do not display warning: assume "yes".')
@pass_config
def drop(config, yes):
    '''
    Drop the migrations table.

    BACK UP YOUR DATA BEFORE USING THIS COMMAND!

    This destroys all metadata about what migrations have and have not been
    applied. This is typically only useful when debugging.
    '''

    db = _connect_db(config)
    cursor = db.cursor()

    warning = 'WARNING: This will drop all migrations metadata!'
    click.echo(click.style(warning, fg='red'))
    confirmation = 'Are you 100% positive that you want to do this?'

    if not (yes or click.confirm(confirmation)):
        raise click.Abort()

    try:
        cursor.execute('DROP TABLE "agnostic_migrations"')
        db.commit()
        click.secho('Migration table dropped.', fg='green')
    except Exception as e:
        if config.debug:
            raise
        msg = 'Failed to drop migration table: '
        raise click.ClickException(msg + str(e)) from e


@click.command('list')
@pass_config
def list_(config):
    '''
    List migrations.

    This shows migration metadata: migrations that have been applied (and the
    result of that application) and migrations that are pending.

    \b
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

    db = _connect_db(config)
    cursor = db.cursor()

    applied = _get_migration_records(cursor)
    applied_set = {a[0] for a in applied}
    pending = list()

    for pm in _get_pending_migrations(config, cursor):
        if pm not in applied_set:
            pending.append((pm, MIGRATION_STATUS_PENDING, None, None))

    migrations = applied + pending

    try:
        if len(migrations) == 0:
            raise ValueError('no migrations exist')

        column_names = 'Name', 'Status', 'Started At', 'Completed At'
        max_name = len(max(migrations, key=lambda i: len(i[0]))[0])
        max_status = len(max(migrations, key=lambda i: len(i[1]))[1])
        row = '{:<%d} | {:%d} | {:<19} | {:<19}' % (max_name, max_status)

        click.echo(row.format(*column_names))
        click.echo(
            '-' * (max_name + 1) + '+' +
            '-' * (max_status + 2) + '+' +
            '-' * 21 + '+' +
            '-' * 20
        )

        for name, status, started_at, completed_at in migrations:
            if started_at is None:
                started_at = 'N/A'
            elif isinstance(started_at, datetime):
                started_at = started_at.strftime('%Y-%m-%d %H:%I:%S')

            if completed_at is None:
                completed_at = 'N/A'
            elif isinstance(completed_at, datetime):
                completed_at = completed_at.strftime('%Y-%m-%d %H:%I:%S')

            msg = row.format(name, status, started_at, completed_at)

            if status == MIGRATION_STATUS_BOOTSTRAPPED:
                click.echo(msg)
            elif status == MIGRATION_STATUS_FAILED:
                click.secho(msg, fg='red')
            elif status == MIGRATION_STATUS_PENDING:
                click.echo(msg)
            elif status == MIGRATION_STATUS_SUCCEEDED:
                click.secho(msg, fg='green')
            else:
                raise ValueError('Invalid migration status: "{}".'
                                 .format(status))
    except Exception as e:
        if config.debug:
            raise
        raise click.ClickException('Cannot list migrations: ' + str(e)) from e


@click.command()
@click.option('--backup/--no-backup',
              default=True,
              help='Automatically backup the database before running ' \
                   'migrations, and in the event of a failure, automatically ' \
                   'restore from that backup. (default: --backup).')
@pass_config
def migrate(config, backup):
    '''
    Run pending migrations.
    '''

    db = _connect_db(config)
    db.autocommit = True
    cursor = db.cursor()

    if _any_failed_migrations(cursor):
        raise click.ClickException(
            click.style('Cannot run due to previously failed migrations.',
                        fg='red')
        )

    pending = _get_pending_migrations(config, cursor)
    total = len(pending)

    if total == 0:
        raise click.ClickException(
            click.style('There are no pending migrations.', fg='green')
        )

    if backup:
        backup_file = tempfile.NamedTemporaryFile('w', delete=False)
        click.echo(
            'Backing up schema "%s" to "%s".' %
            (config.schema, backup_file.name)
        )
        _wait_for(_backup(config, backup_file))
        backup_file.close()

    click.echo('About to run %d migration%s in schema "%s":' %
               (total, 's' if total > 1 else '', config.schema))

    try:
        _run_migrations(config, cursor, pending)
    except Exception as e:
        click.secho('Migration failed because:', fg='red')
        click.echo(str(e))
        db.close()

        if backup:
            click.secho('Will try to restore from backup…', fg='red')

            try:
                _clear_schema(config)
                _wait_for(_restore(config, open(backup_file.name, 'r')))
                click.secho('Restored from backup.', fg='green')
            except Exception as e2:
                msg = 'Could not restore from backup: %s' % str(e2)
                click.secho(msg, fg='red', bold=True)

        if config.debug:
            raise

        raise click.Abort() from e

    click.secho('Migrations completed successfully.', fg='green')

    if backup:
        click.echo('Removing backup "%s".' % backup_file.name)
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

    click.echo('Creating snapshot...')

    _wait_for(_make_snapshot(config, outfile))
    _migration_insert_sql(config, outfile)

    click.secho('Snapshot written to "%s".' % outfile.name, fg='green')


@click.command()
@click.option('-y', '--yes',
              is_flag=True,
              help='Do not display warning: assume "yes".')
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

    Note: you may find it useful to set up a database/schema for testing
    separate from the one that you use for development; this allows you to test
    repeatedly without disrupting your development work.
    '''

    # Create a temporary file for holding the migrated schema.
    temp_snapshot = tempfile.TemporaryFile('w+')

    # Make sure the user understands what is about to happen.
    warning = 'WARNING: This will drop the schema "%s"!' % config.schema
    click.echo(click.style(warning, fg='red'))
    confirmation = 'Are you 100% positive that you want to do this?'

    if not (yes or click.confirm(confirmation)):
        raise click.Abort()

    # Load the current schema.
    click.echo('Dropping schema "%s".' % config.schema)
    _clear_schema(config)

    click.echo('Loading current snapshot "%s".' % current.name)
    _wait_for(_load_snapshot(config, current))

    # Run migrations on current schema.
    db = _connect_db(config)
    db.autocommit = True
    cursor = db.cursor()

    pending = _get_pending_migrations(config, cursor)
    total = len(pending)
    click.echo('About to run %d migration%s in schema "%s":' %
               (total, 's' if total > 1 else '', config.schema))
    _run_migrations(config, cursor, pending)
    click.echo('Finished migrations.')

    # Dump the migrated schema to the temp file.
    click.echo('Snapshotting the migrated schema.')
    _wait_for(_make_snapshot(config, temp_snapshot))
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


cli.add_command(bootstrap)
cli.add_command(drop)
cli.add_command(snapshot)
cli.add_command(list_)
cli.add_command(test)
cli.add_command(migrate)


def _any_failed_migrations(cursor):
    ''' Return True if there are any failed migrations, false otherwise. '''

    cursor.execute('''
        SELECT COUNT(*) FROM "agnostic_migrations"
        WHERE "status" LIKE '%s';
    ''' % MIGRATION_STATUS_FAILED)

    return cursor.fetchone()[0] != 0


def _backup(config, backup_file):
    ''' Backup the schema to the given file handle. '''

    if config.type == 'postgres':
        env = {'PGPASSWORD': config.password}

        command = [
            'pg_dump',
            '-h', config.host,
            '-p', str(config.port),
            '-U', config.user,
            config.schema,
        ]

        process = subprocess.Popen(
            command,
            env=env,
            stdout=backup_file,
            stderr=subprocess.PIPE
        )

        return process

    else:
        raise ValueError('Database type "%s" not supported.' % config.type)


def _bootstrap_migration(type_, cursor, migration):
    '''
    Insert a migration into the migrations table and mark it as having been
    boostrapped.
    '''

    params = (migration, MIGRATION_STATUS_BOOTSTRAPPED)

    if type_ == 'postgres':
        cursor.execute('''
            INSERT INTO "agnostic_migrations"
            VALUES (%s, %s, NOW(), NOW())
            ''',
            params
        )
    else:
        raise ValueError('Database type "%s" not supported.' % type_)


def _clear_schema(config):
    ''' Drop all tables (and related objects) in the the current schema. '''

    if config.type == 'postgres':
        db = _connect_db(config)
        db.autocommit = True
        cursor = db.cursor()

        cursor.execute('''
            SELECT tablename FROM pg_tables
             WHERE tableowner = %s
               AND schemaname != 'pg_catalog'
               AND schemaname != 'information_schema'
        ''', (config.user,))

        tables = ['"%s"' % row[0] for row in cursor.fetchall()]

        if len(tables) > 0:
            cursor.execute('DROP TABLE %s CASCADE' % ','.join(tables))

        cursor.execute('''
            SELECT relname FROM pg_class
             WHERE relkind = 'S'
        ''')

        sequences = ['"%s"' % row[0] for row in cursor.fetchall()]

        if len(sequences) > 0:
            cursor.execute('DROP SEQUENCE %s CASCADE' % ','.join(sequences))

        db.close()
    else:
        raise ValueError('Database type "%s" not supported.' % config.type)


def _connect_db(config):
    ''' Return a DB connection. '''

    if config.type == 'postgres':
        try:
            psycopg2 = importlib.__import__('psycopg2')
        except ImportError as e:
            msg = 'psycopg2 module is required for Postgres.'
            raise click.ClickException(msg) from e

        try:
            return psycopg2.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.schema
            )
        except Exception as e:
            if config.debug:
                raise
            else:
                err = 'Unable to connect to database: %s'
                raise click.ClickException(err % str(e)) from e
    else:
        raise ValueError('Database type "%s" not supported.' % config.type)


def _get_create_table_sql(type_):
    ''' Return a SQL DDL statement for creating the migration table. '''

    if type_ == 'postgres':
        return '''
            CREATE TABLE "agnostic_migrations" (
                name VARCHAR(255) PRIMARY KEY,
                status VARCHAR(255),
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        '''
    else:
        raise ValueError('Database type "%s" not supported.' % type_)


def _get_default_port(type_):
    ''' Return the default port number for the given type of database. '''

    try:
        return DEFAULT_PORTS[type_]
    except KeyError as ke:
        raise ValueError('Database type "%s" not supported.' % type_) from ke


def _get_migration_records(cursor):
    ''' Return records from the migration table. '''

    cursor.execute('''
            SELECT * FROM "agnostic_migrations"
            ORDER BY "started_at", "name"
        ''')

    return cursor.fetchall()


def _get_pending_migrations(config, cursor):
    '''
    Return a list of pending migrations in the order they should be applied.
    '''

    applied_migrations = {m[0] for m in _get_migration_records(cursor)}
    migration_files = _list_migration_files(config.migrations_dir)

    return [m for m in migration_files if m not in applied_migrations]


def _list_migration_files(migrations_dir, sub_path=''):
    '''
    List all of the migration files in the specified directory.

    Migration files are returned as paths relative to ``migrations_dir``,
    sorted alphanumerically.
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


def _load_snapshot(config, snapshot):
    '''
    Load a schema snapshot.

    Stderr should be connected to a pipe so that the caller can read error
    messages, if any.
    '''

    if config.type == 'postgres':
        env = {'PGPASSWORD': config.password}

        command = [
            'psql',
            '-h', config.host,
            '-p', str(config.port),
            '-U', config.user,
            '-v', 'ON_ERROR_STOP=1', # Fail fast if an error occurs.
            config.schema,
        ]

        process = subprocess.Popen(
            command,
            env=env,
            stdin=snapshot,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        return process

    else:
        raise ValueError('Database type "%s" not supported.' % config.type)


def _make_snapshot(config, outfile):
    '''
    Write a snapshot to ``outfile``.

    This should write the schema only (no data) in a deterministic way (so that
    the same schema dumped on a different host or at a different time would
    produce a byte-for-byte identical snapshot).

    Stderr should be connected to a pipe so that the caller can read error
    messages, if any.
    '''

    if config.type == 'postgres':
        env = {'PGPASSWORD': config.password}

        command = [
            'pg_dump',
            '-h', config.host,
            '-p', str(config.port),
            '-U', config.user,
            '-s', # dump schema only
            '-x', # don't dump grant/revoke statements
            '-O', # don't dump ownership commands
            '--no-tablespaces',
            config.schema,
        ]

        process = subprocess.Popen(
            command,
            env=env,
            stdout=outfile,
            stderr=subprocess.PIPE
        )

        return process

    else:
        raise ValueError('Database type "%s" not supported.' % config.type)


def _migration_insert_sql(config, outfile):
    ''' Write SQL for inserting migration metadata to `outfile`. '''

    db = _connect_db(config)
    cursor = db.cursor()
    insert = "INSERT INTO agnostic_migrations VALUES ('{}', '{}', NOW(), NOW());\n"

    for migration in _get_migration_records(cursor):
        outfile.write(insert.format(migration[0], MIGRATION_STATUS_SUCCEEDED))


def _restore(config, backup_file):
    ''' Restore the schema from the given file handle. '''

    if config.type == 'postgres':
        env = {'PGPASSWORD': config.password}

        command = [
            'psql',
            '-h', config.host,
            '-p', str(config.port),
            '-U', config.user,
            '-v', 'ON_ERROR_STOP=1', # Fail fast if an error occurs.
            config.schema,
        ]

        process = subprocess.Popen(
            command,
            env=env,
            stdin=backup_file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        return process

    else:
        raise ValueError('Database type "%s" not supported.' % config.type)


def _run_migrations(config, cursor, migrations):
    ''' Run the specified migrations in the given order. '''

    total = len(migrations)
    mig2file = lambda m: os.path.join(config.migrations_dir, '%s.sql' % m)

    for index, migration in enumerate(migrations):
        click.echo(' * Running migration ' +
                   click.style(migration, bold=True) +
                   ' (%d/%d)' % (index + 1, total))

        cursor.execute('''
            INSERT INTO "agnostic_migrations" ("name", "status", "started_at")
            VALUES (%(name)s, %(status)s, NOW())
        ''', {'name': migration, 'status': MIGRATION_STATUS_FAILED})

        _wait_for(_run_migration_file(config, open(mig2file(migration), 'r')))

        cursor.execute('''
            UPDATE "agnostic_migrations"
            SET "status" = %(status)s, "completed_at" = NOW()
            WHERE "name" = %(name)s
        ''', {'name': migration, 'status': MIGRATION_STATUS_SUCCEEDED})


def _run_migration_file(config, migration_file):
    ''' Run a single migration file and return a process. '''

    if config.type == 'postgres':
        env = {'PGPASSWORD': config.password}

        command = [
            'psql',
            '-h', config.host,
            '-p', str(config.port),
            '-U', config.user,
            '-v', 'ON_ERROR_STOP=1', # Fail fast if an error occurs.
            config.schema,
        ]

        process = subprocess.Popen(
            command,
            env=env,
            stdin=migration_file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        return process

    else:
        raise ValueError('Database type "%s" not supported.' % config.type)


def _wait_for(process):
    ''' Wait for ``process`` to finish and check the exit code. '''

    process.wait()

    if process.returncode != 0:
        msg = 'failed to run external tool "%s" (exit %d):\n%s'

        params = (
            process.args[0],
            process.returncode,
            process.stderr.read().decode('utf8')
        )

        raise click.ClickException(msg % params)


if __name__ == '__main__':
    cli()

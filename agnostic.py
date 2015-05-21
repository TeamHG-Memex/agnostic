import os
from urllib.parse import urlparse

import click


POSTGRES_DEFAULT_PORT = 5432

MIGRATION_STATUS_BOOTSTRAPPED = "bootstrapped"
MIGRATION_STATUS_SUCCEEDED = "succeeded"
MIGRATION_STATUS_FAILED = "failed"


class Config(object):
    ''' Keeps track of configuration. '''

    def __init__(self):
        self.db = None
        self.host = None
        self.migrations_dir = None
        self.password = None
        self.port = None
        self.schema = None
        self.type = None
        self.user = None


pass_config = click.make_pass_decorator(Config, ensure=True)


def validate_not_none(ctx, param, value):
    ''' Validate that an option is not None. '''

    if value is None:
        raise click.BadParameter('a value is required')
    else:
        return value


@click.group()
@click.option('-t', '--type',
              envvar='AGNOSTIC_TYPE',
              metavar='<type>',
              callback=validate_not_none,
              type=click.Choice(['postgres']),
              help='Type of database.')
@click.option('-h', '--host',
              default='localhost',
              envvar='AGNOSTIC_HOST',
              metavar='<host>',
              callback=validate_not_none,
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
              callback=validate_not_none,
              help='Database username.')
@click.option('-p', '--password',
              envvar='AGNOSTIC_PASSWORD',
              metavar='<pass>',
              callback=validate_not_none,
              prompt='Database password',
              hide_input=True,
              help='Database password. If omitted, the password must be ' \
                   'entered on stdin.')
@click.option('-s', '--schema',
              envvar='AGNOSTIC_SCHEMA',
              metavar='<schema>',
              callback=validate_not_none,
              help='Name of database schema.')
@click.option('-d', '--migrations-dir',
              default='migrations',
              envvar='AGNOSTIC_MIGRATIONS_DIR',
              metavar='<dir>',
              callback=validate_not_none,
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
    config.port = port
    config.schema = schema
    config.type = type
    config.user = user
    config.migrations_dir = migrations_dir


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
        raise click.UsageError('Failed to create migration table: ' + str(e))

    if load_existing:
        for migration in _list_migration_files(config.migrations_dir):
            try:
                _bootstrap_migration(config.type, cursor, migration)
            except Exception as e:
                if config.debug:
                    raise
                raise click.UsageError('Failed to load existing migrations: '
                                       + str(e))

    db.commit()
    click.secho('Migraiton table created.', fg='green')


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

    if yes or click.confirm('Are you 100% positive that you want to do this?'):
        try:
            cursor.execute('DROP TABLE "agnostic_migrations"')
            db.commit()
            click.secho('Migration table dropped.', fg='green')
        except Exception as e:
            if config.debug:
                raise
            raise click.UsageError('Failed to drop migration table: ' + str(e))


@click.command()
@pass_config
def snapshot(config):
    '''
    Take a snapshot of the current schema.
    '''
    click.echo('snapshot')


@click.command('list')
@pass_config
def list_(config):
    '''
    List migrations.

    This shows migration metadata: which migrations have been applied and the
    results of those migrations. Each migration has one of the following
    statuses:

    \b
        * bootstrapped: a migration that was inserted during the bootstrap
          process.
        * failed: the migration did not apply cleanly; the migrations system
          will not be able to operate until this rectified, typically by
          restoring from a backup.
        * succeeded: the migration applied cleanly.

    Migrations are ordered by the ``started_at`` timestamp.
    '''

    db = _connect_db(config)
    cursor = db.cursor()

    try:
        migrations = _get_migration_records(cursor)

        if len(migrations) == 0:
            raise ValueError('no migrations exist')

        column_names = 'Name', 'Status', 'Started At', 'Completed At'
        max_name_len = len(max(migrations, key=lambda i: len(i[0]))[0])
        max_status_len = len(max(migrations, key=lambda i: len(i[1]))[1])
        row = '{:<%d} | {:%d} | {:<19} | {:<19}' % (max_name_len, max_status_len)

        click.echo(row.format(*column_names))
        click.echo(
            '-' * (max_name_len + 1) + '+' +
            '-' * (max_status_len + 2) + '+' +
            '-' * 21 + '+' +
            '-' * 20
        )

        for name, status, started_at, completed_at in migrations:
            started_at = started_at.strftime('%Y-%m-%d %H:%I:%S')
            completed_at = completed_at.strftime('%Y-%m-%d %H:%I:%S')
            msg = row.format(name, status, started_at, completed_at)

            if status == MIGRATION_STATUS_BOOTSTRAPPED:
                click.echo(msg)
            elif status == MIGRATION_STATUS_FAILED:
                click.secho(msg, fg='red')
            elif status == MIGRATION_STATUS_SUCCEEDED:
                click.secho(msg, fg='green')
            else:
                raise ValueError('Invalid migration status: "{}".'
                                 .format(status))
    except Exception as e:
        if config.debug:
            raise
        raise click.UsageError('Cannot list migrations: ' + str(e))


@click.command()
@pass_config
def test(config):
    '''
    Test pending migrations.
    '''
    click.echo('test')


@click.command()
@pass_config
def migrate(config):
    '''
    Run pending migrations.
    '''
    click.echo('migrate')


cli.add_command(bootstrap)
cli.add_command(drop)
cli.add_command(snapshot)
cli.add_command(list_)
cli.add_command(test)
cli.add_command(migrate)


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
        raise ValueError('Database type "%s" not supported.' % config.type)


def _connect_db(config):
    ''' Return a DB connection. '''

    if config.port is not None:
        port = config.port
    else:
        port = POSTGRES_DEFAULT_PORT

    if config.type == 'postgres':
        try:
            import psycopg2
        except ImportError:
            raise click.UsageError('psycopg2 module is required for Postgres.')

        return psycopg2.connect(
            host=config.host,
            port=port,
            user=config.user,
            password=config.password,
            database=config.schema
        )

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


def _get_migration_records(cursor):
    ''' Return records from the migration table. '''

    cursor.execute('''
            SELECT * FROM "agnostic_migrations"
            ORDER BY "started_at", "name"
        ''')

    return cursor.fetchall()

def _list_migration_files(migrations_dir, sub_path=''):
    '''
    List all of the migration files in the specified directory.

    Migration files are returned as paths relative to ``migrations_dir``,
    sorted alphanumerically.
    '''

    migration_prefix_len = len(migrations_dir) + 1
    current_dir = os.path.join(migrations_dir, sub_path)

    for dir_entry in sorted(os.listdir(current_dir)):
        dir_entry_path = os.path.join(current_dir, dir_entry)

        if os.path.isfile(dir_entry_path):
            yield dir_entry_path[migration_prefix_len:]
        elif os.path.isdir(dir_entry_path):
            new_sub_path = os.path.join(sub_path, dir_entry)
            yield from _list_migration_files(migrations_dir, new_sub_path)

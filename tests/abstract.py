from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timedelta
import logging
import os
import shutil
import tempfile
import unittest
import warnings

from click.testing import CliRunner

import agnostic
import agnostic.cli


logging.basicConfig()


class AbstractDatabaseTest(metaclass=ABCMeta):
    '''
    Base class for database integration tests.

    Concrete subclasses should inherit from (AbstractDatabaseTest,
    unittest.TestCase).
    '''

    @property
    @abstractmethod
    def db_type(self):
        ''' The database type as a string. '''

    @property
    @abstractmethod
    def default_db(self):
        ''' The database to connect when dropping/creating a test database. '''

    def __init__(self, *args, **kwargs):
        ''' Constructor. '''

        self._migrations_inserted = 0
        self._param = '%s'
        db_type = self.db_type.upper()
        host_env = '{}_HOST'.format(db_type)
        port_env = '{}_PORT'.format(db_type)
        test_db_env = '{}_TEST_DB'.format(db_type)
        self._host = os.getenv(host_env, 'localhost')
        self._port = os.getenv(port_env, None)
        self._test_db = os.getenv(test_db_env, 'testdb')
        super().__init__(*args, **kwargs)

    @abstractmethod
    def connect_db(self, user, password, database):
        ''' Return a connection to the specified database. '''

    def create_migrations_dir(self, fixture_name=None, migration_names=None):
        '''
        Create a temporary migrations directory by selecting a set of
        ``migrations`` from the set named ``fixture_name``.

        If ``fixture_name`` is None or ``migration_names`` is None/empty, then
        an empty directory is created.
        '''
        logging.info('Creating migrations fixture: %s', fixture_name)
        tempdir = tempfile.mkdtemp()

        if fixture_name is not None and \
           migration_names is not None and \
           len(migration_names) > 0:

            base_path = os.path.join(
                os.path.dirname(__file__),
                'fixtures',
                '{}_{}'.format(fixture_name, self.db_type)
            )

            for migration_name in migration_names:
                src = os.path.join(base_path, '{}.sql'.format(migration_name))
                shutil.copy(src, tempdir)

        return tempdir

    def create_migrations_table(self, cursor):
        ''' Create a migrations table. '''
        logging.info('Creating migrations table')
        table_sql = agnostic.MIGRATION_TABLE_SQL
        cursor.execute(table_sql)

    def get_credentials_from_env(self):
        '''
        Get username & password from the environment.

        Skip the current test if these environment variables are not set.
        '''

        try:
            user = os.environ['{}_USER'.format(self.db_type.upper())]
            password = os.environ['{}_PASSWORD'.format(self.db_type.upper())]
        except KeyError as key:
            message = 'Missing environment variable: {}'
            raise unittest.SkipTest(message.format(key.args[0]))

        return user, password

    @contextmanager
    def get_db(self, database):
        ''' Return a new connection and cursor to a database. '''
        user, password = self.get_credentials_from_env()
        logging.info('Connecting to database "%s" as user "%s"', database, user)

        try:
            db = self.connect_db(user, password, database)
        except Exception as e:
            raise
            msg = 'Cannot connect to {}: {}'
            raise unittest.SkipTest(msg.format(self.db_type, e))

        cursor = db.cursor()

        try:
            yield db, cursor
        finally:
            try:
                db.close()
            except:
                pass

    def get_base_command(self):
        ''' Get command line base options. '''
        user, password = self.get_credentials_from_env()

        command = [
            '-t', self.db_type,
            '-h', self._host,
            '-u', user,
            '--password', password,
            '-d', self._test_db,
        ]

        if self._port is not None:
            command.append('-p')
            command.append(self._port)

        return command

    def get_migration(self, fixture_name, migration_name):
        ''' Get the text of a migration script. '''

        migration_path = os.path.join(
            os.path.dirname(__file__),
            'fixtures',
            '{}_{}'.format(fixture_name, self.db_type),
            '{}.sql'.format(migration_name)
        )

        with open(migration_path) as migration_file:
            migration = migration_file.read()

        return migration

    def get_snapshot(self):
        ''' Take a snapshot and return as a file path. '''
        current_snap_file, current_snap_path = tempfile.mkstemp()
        os.close(current_snap_file)
        result = self.run_cli(['snapshot', current_snap_path])
        logging.info('Created snapshot: %s', current_snap_path)
        return current_snap_path

    def insert_migration(self, cursor, name, status,
                         started=None, completed=None):
        ''' Insert a row into the migration table. '''
        logging.info('Inserting migration: %s [%s]', name, status)
        base_date = datetime(year=2016, month=1, day=1)

        if started is None:
            offset = timedelta(minutes=1) * self._migrations_inserted
            started = base_date + offset
            self._migrations_inserted += 1

        if completed is None:
            completed = started + timedelta(seconds=59)

        query = 'INSERT INTO agnostic_migrations VALUES ({}, {}, {}, {})' \
            .format(self._param, self._param, self._param, self._param)
        cursor.execute(query, (name, status, started, completed))

    def run_cli(self, args, migrations_dir=None):
        ''' Run CLI by providing default flags and supplied ``args``. '''
        logging.info('Running CLI with args: %r', args)
        command = self.get_base_command()
        command.extend([
            '-m', migrations_dir or self.create_migrations_dir(),
        ])

        if self._port is not None:
            command.append('-p')
            command.append(self._port)

        command.extend(args)

        result = CliRunner().invoke(agnostic.cli.main, command)

        if result.exception is not None and \
           not isinstance(result.exception, SystemExit):
            logging.error('== run_cli exception ==')
            logging.error('COMMAND: %s', command)
            logging.error('EXIT CODE: %s', result.exit_code)
            logging.error('OUTPUT:\n%s', result.output)
            raise result.exception

        return result

    def run_migrations(self, cursor, migration_fixture, migration_names):
        '''
        Run the specified migration scripts.

        This roughly emulates an ORM building tool.
        '''
        logging.info('Simulating ORM build')
        for migration_name in migration_names:
            self.insert_migration(cursor, migration_name, 'bootstrapped')
            migration = self.get_migration(migration_fixture, migration_name)
            agnostic.cli._run_sql(cursor, migration)

    def setUp(self):
        ''' Create test database. '''
        logging.info('Creating test database')
        with self.get_db(self.default_db) as (db, cursor):
            with warnings.catch_warnings():
                # Don't show a warning if the database doesn't exist.
                warnings.simplefilter('ignore')
                drop_sql = 'DROP DATABASE IF EXISTS {}'
                cursor.execute(drop_sql.format(self._test_db))

            cursor.execute('CREATE DATABASE {}'.format(self._test_db))

    @abstractmethod
    def table_columns(self, cursor, database, table_name):
        ''' Return a list of columns in the specified table. '''

    @abstractmethod
    def table_exists(self, cursor, database, table_name):
        ''' Return true if the specified table exists. '''

    def test_bootstrap_creates_migration_table(self):
        ''' The "bootstrap" CLI command creates a migrations table. '''

        with self.get_db(self._test_db) as (db, cursor):
            table_exists = self.table_exists(
                cursor,
                self._test_db,
                'agnostic_migrations'
            )
            self.assertFalse(table_exists)

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table',
        ])

        # Should have a table after bootstrapping.
        result = self.run_cli(['bootstrap'], migrations_dir)
        self.assertEqual(0, result.exit_code)

        with self.get_db(self._test_db) as (db, cursor):
            table_exists = self.table_exists(
                cursor,
                self._test_db,
                'agnostic_migrations'
            )
            self.assertTrue(table_exists)

            # The table should contain a row for the bootstrapped migration.
            cursor.execute(
                'SELECT * FROM agnostic_migrations ORDER BY started_at'
            )

            migrations = cursor.fetchall()
            self.assertEqual(1, len(migrations))

        name, status, started_at, completed_at = migrations[0]
        self.assertEqual('1_create_employee_table', name)
        self.assertEqual('bootstrapped', status)
        self.assertIsNotNone(started_at)
        self.assertIsNotNone(completed_at)

    def test_bootstrap_does_not_recreate_migrations_table(self):
        '''
        The "bootstrap" CLI command does not recreate the migrations table.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)

        result = self.run_cli(['bootstrap'])
        self.assertNotEqual(0, result.exit_code)

    def test_drop_deletes_migration_table(self):
        ''' The "drop" command deletes the migrations table. '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)

        # Should not have a table after dropping.
        result = self.run_cli(['drop', '-y'])
        self.assertEqual(0, result.exit_code)

        with self.get_db(self._test_db) as (db, cursor):
            table_exists = self.table_exists(
                cursor,
                self._test_db,
                'agnostic_migrations'
            )
            self.assertFalse(table_exists)

    def test_drop_error_if_no_migration_table(self):
        '''
        The "drop" command fails gracefully if there is no migrations table.
        '''

        result = self.run_cli(['drop', '-y'])
        self.assertNotEqual(0, result.exit_code)

    def test_list_shows_migrations(self):
        '''
        The "list" command shows completed and pending migrations.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            self.insert_migration(cursor, 'foo', 'bootstrapped')
            self.insert_migration(cursor, 'bar', 'succeeded')

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table'
        ])

        result = self.run_cli(['list'], migrations_dir)
        lines = result.output.split(os.linesep)

        # Assertions against the text output: these are unavoidably brittle.
        # Lines 1 and 2 are table headers and not interesting. Lines 3-5 are
        # migration data.
        self.assertEqual(6, len(lines))
        self.assertIn('foo',                     lines[2])
        self.assertIn('bootstrapped',            lines[2])
        self.assertIn('bar',                     lines[3])
        self.assertIn('succeeded',               lines[3])
        self.assertIn('1_create_employee_table', lines[4])
        self.assertIn('pending',                 lines[4])
        self.assertIn('N/A',                     lines[4])

    def test_list_failed_migrations(self):
        '''
        The "list" command shows failed migrations.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            self.insert_migration(cursor, 'foo', 'bootstrapped')
            self.insert_migration(cursor, 'bar', 'succeeded')
            self.insert_migration(cursor, 'baz', 'failed')

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table'
        ])

        result = self.run_cli(['list'], migrations_dir)
        lines = result.output.split(os.linesep)

        # Assertions against the text output: these are unavoidably brittle.
        # Lines 1 and 2 are table headers and not interesting. Lines 3-5 are
        # migration data.
        self.assertEqual(7, len(lines))
        self.assertIn('foo',                     lines[2])
        self.assertIn('bootstrapped',            lines[2])
        self.assertIn('bar',                     lines[3])
        self.assertIn('succeeded',               lines[3])
        self.assertIn('baz',                     lines[4])
        self.assertIn('failed',                  lines[4])
        self.assertIn('1_create_employee_table', lines[5])
        self.assertIn('pending',                 lines[5])
        self.assertIn('N/A',                     lines[5])

    def test_migrate_runs_pending_migrations(self):
        '''
        The "migrate" command runs pending migrations.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            migration_name = '1_create_employee_table'
            self.insert_migration(cursor, migration_name, 'succeeded')
            migration1 = self.get_migration('employee', migration_name)
            agnostic.cli._run_sql(cursor, migration1)

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table',
            '2_rename_phone_to_home',
            '3_add_cell_phone',
        ])

        result = self.run_cli(['migrate'], migrations_dir)

        with self.get_db(self._test_db) as (db, cursor):
            # The migration should change the last column from "home" to
            # "phone_home" and add a column called "phone_cell".
            columns = self.table_columns(cursor, self._test_db, 'employee')
            self.assertEqual(5, len(columns))
            self.assertEqual(columns[3], 'phone_home')
            self.assertEqual(columns[4], 'phone_cell')

            # Migration metadata should be updated.
            cursor.execute('''
                SELECT status FROM agnostic_migrations
                WHERE name = '2_rename_phone_to_home' OR
                      name = '3_add_cell_phone'
            ''')
            (status1,), (status2,) = cursor.fetchall()
            self.assertEqual('succeeded', status1)
            self.assertEqual('succeeded', status2)

    def test_migrate_fails_if_earlier_migrations_failed(self):
        '''
        The "migrate" command does not run if earlier migrations failed.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            self.insert_migration(cursor, 'foo', 'bootstrapped')
            self.insert_migration(cursor, 'bar', 'succeeded')
            self.insert_migration(cursor, 'baz', 'failed')

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table',
            '2_rename_phone_to_home',
            '3_add_cell_phone',
        ])

        result = self.run_cli(['migrate'], migrations_dir)
        self.assertNotEqual(result.exit_code, 0)

    def test_migrate_fails_on_invalid_sql(self):
        '''
        The "migrate" command fails if a migration contains invalid SQL.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            self.insert_migration(cursor, 'foo', 'bootstrapped')
            self.insert_migration(cursor, 'bar', 'succeeded')

        migrations_dir = self.create_migrations_dir('employee', ['1_invalid'])

        result = self.run_cli(['migrate'], migrations_dir)
        self.assertNotEqual(result.exit_code, 0)

    def test_migrate_no_error_if_nothing_pending(self):
        '''
        The "migrate" command exits with code 0 if no migrations are pending.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            migration_name = '1_create_employee_table'
            self.insert_migration(cursor, migration_name, 'succeeded')

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table',
        ])

        result = self.run_cli(['migrate'], migrations_dir)
        self.assertEqual(0, result.exit_code)

    def test_snapshot_dumps_structure(self):
        '''
        The "snapshot" command dumps structures but no data.
        '''

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            migration_name = '1_create_employee_table'
            self.insert_migration(cursor, migration_name, 'succeeded')
            migration = self.get_migration('employee', migration_name)
            agnostic.cli._run_sql(cursor, migration)

            cursor.execute('''
                INSERT INTO employee VALUES (1, 'John', 'Doe', '2025551234')
            ''')

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table',
        ])

        snap_file, snap_path = tempfile.mkstemp()
        os.close(snap_file)

        result = self.run_cli(['snapshot', snap_path], migrations_dir)

        with open(snap_path) as snap_file:
            snapshot = snap_file.read()

        self.assertRegexpMatches(snapshot, 'CREATE TABLE.*employee')
        self.assertNotIn('John', snapshot)
        self.assertNotIn('Doe', snapshot)
        self.assertNotIn('12025551234', snapshot)

    def test_tester_succeeds_for_correct_migrations(self):
        '''
        The "test" command succeeds if all migrations are written correctly.
        '''

        migrations = [
            '1_create_employee_table',
            '2_rename_phone_to_home',
            '3_add_cell_phone',
        ]

        with self.get_db(self._test_db) as (db, cursor):
            self.create_migrations_table(cursor)
            self.run_migrations(cursor, 'employee', migrations[0:1])
            current_snap = self.get_snapshot()
            self.run_migrations(cursor, 'employee', migrations[1:])
            target_snap = self.get_snapshot()

        migrations_dir = self.create_migrations_dir('employee', migrations)

        result = self.run_cli(
            ['test', '-y', current_snap, target_snap],
            migrations_dir
        )

        self.assertEqual(0, result.exit_code)

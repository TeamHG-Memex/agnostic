from contextlib import contextmanager
from datetime import datetime, timedelta
import os
import re
import shutil
import tempfile
import traceback
import unittest

from click import ClickException
from click.testing import CliRunner
import psycopg2

import agnostic
import agnostic.cli


class TestPostgreSql(unittest.TestCase):
    '''
    Integration tests for Agnostic Database Migrations & PostgreSQL.
    '''

    DEFAULT_DB = 'postgres'
    DB_TYPE = 'postgres'
    TEST_DB = 'testdb'

    def __init__(self, *args, **kwargs):
        ''' Constructor. '''

        self._migrations_inserted = 0

        super().__init__(*args, **kwargs)

    def create_migrations_dir(self, fixture_name=None, migration_names=None):
        '''
        Create a temporary migrations directory by selecting a set of
        ``migrations`` from the set named ``fixture_name``.

        If ``fixture_name`` is None or ``migration_names`` is None/empty, then
        an empty directory is created.
        '''
        tempdir = tempfile.mkdtemp()

        if fixture_name is not None and \
           migration_names is not None and \
           len(migration_names) > 0:

            base_path = os.path.join(
                os.path.dirname(__file__),
                'fixtures',
                'migrations_{}'.format(fixture_name)
            )

            for migration_name in migration_names:
                src = os.path.join(base_path, '{}.sql'.format(migration_name))
                shutil.copy(src, tempdir)

        return tempdir

    def create_migrations_table(self, cursor):
        ''' Create a migrations table. '''

        table_sql = agnostic.MIGRATION_TABLE_SQL
        cursor.execute(table_sql)

    def get_credentials_from_env(self):
        '''
        Get username & password from the environment.

        Skip the current test if these environment variables are not set.
        '''

        try:
            user = os.environ['POSTGRES_USER']
            password = os.environ['POSTGRES_PASSWORD']
        except KeyError as key:
            message = 'Missing environment variable: {}'
            raise unittest.SkipTest(message.format(key.args[0]))

        return user, password

    @contextmanager
    def get_db(self, database):
        ''' Return a new connection and cursor to a database. '''

        user, password = self.get_credentials_from_env()

        try:
            db = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=os.getenv('POSTGRES_PORT', None),
                user=user,
                password=password,
                database=database
            )
        except Exception as e:
            raise unittest.SkipTest('Cannot connect to Postgres: {}'.format(e))

        db.autocommit = True
        cursor = db.cursor()

        try:
            yield db, cursor
        finally:
            db.close()

    def get_migration(self, fixture_name, migration_name):
        ''' Get the text of a migration script. '''

        migration_path = os.path.join(
            os.path.dirname(__file__),
            'fixtures',
            'migrations_{}'.format(fixture_name),
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

        return current_snap_path

    def insert_migration(self, cursor, name, status,
                         started=None, completed=None):
        ''' Insert a row into the migration table. '''

        base_date = datetime(year=2016, month=1, day=1)

        if started is None:
            offset = timedelta(minutes=1) * self._migrations_inserted
            started = base_date + offset
            self._migrations_inserted += 1

        if completed is None:
            completed = started + timedelta(seconds=59)

        cursor.execute(
            "INSERT INTO agnostic_migrations VALUES (%s, %s, %s, %s)",
            (name, status, started, completed)
        )

    def run_cli(self, args, migrations_dir=None):
        ''' Run CLI by providing default flags and supplied ``args``. '''

        user, password = self.get_credentials_from_env()

        command = [
            '-t', TestPostgreSql.DB_TYPE,
            '-h', os.getenv('POSTGRES_HOST', 'localhost'),
            '-u', user,
            '--password', password,
            '-d', TestPostgreSql.TEST_DB,
            '-m', migrations_dir or self.create_migrations_dir(),
        ]

        if 'POSTGRES_PORT' in os.environ:
            command.extend(['-p', os.environ['POSTGRES_PORT']])

        command.extend(args)

        result = CliRunner().invoke(
            agnostic.cli.main,
            command,
            catch_exceptions=False
        )

        # Nose suppresses stdout for passing tests and displays it only for
        # failed/errored tests.
        print('== run_cli() {}'.format('=' * 57))
        print('COMMAND: {}'.format(command))
        print('EXIT CODE: {}'.format(result.exit_code))
        print('OUTPUT:\n{}'.format(result.output))

        return result

    def run_migrations(self, cursor, migration_fixture, migration_names):
        '''
        Run the specified migration scripts.

        This roughly emulates a schema building tool, e.g. an ORM.
        '''

        for migration_name in migration_names:
            self.insert_migration(cursor, migration_name, 'bootstrapped')
            migration = self.get_migration(migration_fixture, migration_name)
            cursor.execute(migration)

    def setUp(self):
        ''' Create test database. '''

        with self.get_db(TestPostgreSql.DEFAULT_DB) as (db, cursor):
            cursor.execute('DROP DATABASE IF EXISTS {}'.format(
                TestPostgreSql.TEST_DB,
            ))

            cursor.execute('CREATE DATABASE {}'.format(TestPostgreSql.TEST_DB))

    def test_bootstrap_creates_migration_table(self):
        ''' The "bootstrap" CLI command creates a migrations table. '''

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            table_query = '''
                SELECT COUNT(*)
                  FROM pg_tables
                 WHERE tablename LIKE %s
            '''
            table_args = ('agnostic_migrations',)

            migrations_dir = self.create_migrations_dir('employee', [
                '1_create_employee_table',
            ])

            # Should not have a migration table initially.
            cursor.execute(table_query, table_args)
            self.assertEqual(0, cursor.fetchone()[0])

        # Should have a table after bootstrapping.
        result = self.run_cli(['bootstrap'], migrations_dir)
        self.assertEqual(0, result.exit_code)

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            cursor.execute(table_query, table_args)
            self.assertEqual(1, cursor.fetchone()[0])

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

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            self.create_migrations_table(cursor)

        result = self.run_cli(['bootstrap'])
        self.assertNotEqual(0, result.exit_code)

    def test_drop_deletes_migration_table(self):
        ''' The "drop" command deletes the migrations table. '''

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            self.create_migrations_table(cursor)

        # Should not have a table after bootstrapping.
        result = self.run_cli(['drop', '-y'])
        self.assertEqual(0, result.exit_code)

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            table_query = '''
                SELECT COUNT(*)
                  FROM pg_tables
                 WHERE tablename LIKE %s
            '''
            table_args = ('agnostic_migrations',)
            cursor.execute(table_query, table_args)
            r = cursor.fetchone()
            self.assertEqual(0, r[0])

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

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
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

    def test_migrate_runs_pending_migrations(self):
        '''
        The "migrate" command runs pending migrations.
        '''

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            self.create_migrations_table(cursor)
            self.insert_migration(cursor, '1_create_employee_table', 'succeeded')
            migration1 = self.get_migration('employee', '1_create_employee_table')
            cursor.execute(migration1)

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table',
            '2_rename_phone_to_home',
            '3_add_cell_phone',
        ])

        result = self.run_cli(['migrate'], migrations_dir)

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            cursor.execute('''
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_name = 'employee'
              ORDER BY ordinal_position
            ''')

            # The migration should change the last column from "home" to
            # "phone_home" and add a column called "phone_cell".
            columns = cursor.fetchall()
            self.assertEqual(5, len(columns))
            self.assertEqual(columns[3][0], 'phone_home')
            self.assertEqual(columns[4][0], 'phone_cell')

    def test_migrate_error_if_nothing_pending(self):
        '''
        The "migrate" command exits with an error if no migrations are pending.
        '''

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            self.create_migrations_table(cursor)
            self.insert_migration(cursor, '1_create_employee_table', 'succeeded')

        migrations_dir = self.create_migrations_dir('employee', [
            '1_create_employee_table',
        ])

        result = self.run_cli(['migrate'], migrations_dir)
        self.assertNotEqual(0, result.exit_code)

    def test_snapshot_dumps_schema(self):
        '''
        The "snapshot" command dumps schema but no data.
        '''

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
            self.create_migrations_table(cursor)
            self.insert_migration(cursor, '1_create_employee_table', 'succeeded')
            migration1 = self.get_migration('employee', '1_create_employee_table')
            cursor.execute(migration1)

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

    def test_test_succeeds_for_correct_migrations(self):
        '''
        The "test" command succeeds if all migrations are written correctly.
        '''

        migrations = [
            '1_create_employee_table',
            '2_rename_phone_to_home',
            '3_add_cell_phone',
        ]

        with self.get_db(TestPostgreSql.TEST_DB) as (db, cursor):
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


if __name__ == '__main__':
    unittest.main(buffer=True)

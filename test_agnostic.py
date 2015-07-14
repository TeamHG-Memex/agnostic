from datetime import datetime
import os
import random
import re
import unittest
from unittest.mock import MagicMock, Mock, patch

import click
from click.testing import CliRunner

import agnostic


def import_error(missing_dependency):
    ''' Simulate a missing dependency by raising an import error. '''

    def ie_helper(import_name, *args):
        if import_name == missing_dependency:
            raise ImportError()
        else:
            __import__(import_name, *args)

    return ie_helper


def make_file(name, data):
    f = open(name, 'w')
    f.write(data)
    f.close()


class test_agnostic(unittest.TestCase):
    '''
    Unit tests for Agnostic Database Migrations.

    Most of these tests are not great... the interaction with the databases is
    not easy to test against, particularly when the goal of the project is to
    support many different database systems, each of which may require a
    different approach.

    Still, the test coverage still helps weed out a number of silly errors.
    '''

    def cli_args(self, type=None, host=None, port=None, user=None,
                 password=None, schema=None, migrations_dir=None, debug=None):

        ''' A helper for making command line arguments. '''

        args = [
            '-t', type or 'postgres',
            '-h', host or 'localhost',
            '-p', port or 1234,
            '-u', user or 'myuser',
            '--password', password or 'mypass',
            '-s', 'myschema',
            '-m', migrations_dir or 'migrations',
        ]

        if debug:
            args.append('-d')

        return args

    def config_fixture(self, db=None, host=None, migrations_dir=None,
                       password=None, port=None, schema=None, type=None,
                       user=None):

        ''' A helper for making config objects. '''

        config = agnostic.Config()

        config.db = db or Mock()
        config.host = host or 'localhost'
        config.migrations_dir = migrations_dir or 'migrations'
        config.password = password or 'mypass'
        config.port = port or 5942
        config.schema = schema or 'myapp'
        config.type = type or 'postgres'
        config.user = user or 'myuser'

        return config

    def make_cursor(self, connect_db_mock):
        ''' Make a mock database cursor and attach it to a _connect_db mock. '''

        db = Mock()
        cursor = Mock()
        connect_db_mock.return_value = db
        db.cursor.return_value = cursor

        return cursor

    def make_sample_files(self):
        ''' Make some sample files to test against. '''

        os.mkdir('migrations')
        os.mkdir('migrations/01')
        os.mkdir('migrations/04')

        make_file('migrations/01/foo.sql', 'foo')
        make_file('migrations/01/bar.sql', 'bar')
        make_file('migrations/02_foobar.sql', 'foobar')
        make_file('migrations/03_bazbat.sql', 'bazbat')
        make_file('migrations/04/baz.sql', 'baz')
        make_file('migrations/04/bat.sql', 'bat')

    def test_any_failed_migrations_true(self):
        ''' Return True if there are any failed migrations. '''

        cursor = Mock()
        cursor.fetchone.return_value = (1,)

        result = agnostic._any_failed_migrations(cursor)

        self.assertTrue(cursor.execute.called)
        self.assertTrue(result)

    def test_any_failed_migrations_false(self):
        ''' Return False if there are zero failed migrations. '''

        cursor = Mock()
        cursor.fetchone.return_value = (0,)

        result = agnostic._any_failed_migrations(cursor)

        self.assertTrue(cursor.execute.called)
        self.assertFalse(result)

    @patch('subprocess.Popen')
    def test_backup(self, popen_mock):
        ''' Create a backup. '''

        expected_process = 'dummy_process'
        popen_mock.return_value = expected_process
        config = self.config_fixture()
        backup_file = Mock()

        actual_process = agnostic._backup(config, backup_file)

        self.assertEqual(actual_process, expected_process)

    def test_backup_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        config = self.config_fixture(type='bogusdb')
        backup_file = Mock()

        with self.assertRaises(ValueError):
            agnostic._backup(config, backup_file)

    @patch('agnostic._bootstrap_migration')
    @patch('agnostic._connect_db')
    def test_bootstrap(self, connect_db_mock, bootstrap_mig_mock):
        ''' The "bootstrap" CLI command. '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        create_table_re = re.compile(r'create\s+table', flags=re.IGNORECASE)

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['bootstrap']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertEqual(0, result.exit_code)
        self.assertTrue(connect_db_mock.called)
        self.assertTrue(cursor.execute.called)
        self.assertRegex(cursor.execute.call_args[0][0], create_table_re)
        # There are 6 migrations in self.make_sample_files:
        self.assertEqual(6, bootstrap_mig_mock.call_count)

    @patch('agnostic._bootstrap_migration')
    @patch('agnostic._connect_db')
    def test_bootstrap_fail(self, connect_db_mock,
                                         bootstrap_mig_mock):
        '''
        The "bootstrap" CLI fails gracefully if it can't create the migrations
        table or if a particular migration won't run.
        '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.execute.side_effect = ValueError

        # Test failure in creating the migrations table.
        with runner.isolated_filesystem():
            self.make_sample_files()

            cli_args1 = self.cli_args() + ['bootstrap']
            result1 = runner.invoke(agnostic.cli, cli_args1)

            cli_args2 = self.cli_args() + ['--debug', 'bootstrap']
            result2 = runner.invoke(agnostic.cli, cli_args2)

        self.assertNotEqual(0, result1.exit_code)
        self.assertNotEqual(0, result2.exit_code)

        # Non-debug mode returns a non-zero exit code.
        cursor.execute.side_effect = None
        bootstrap_mig_mock.side_effect = ValueError

        with runner.isolated_filesystem():
            self.make_sample_files()

            cli_args3 = self.cli_args() + ['bootstrap']
            result3 = runner.invoke(agnostic.cli, cli_args1)

        self.assertNotEqual(0, result3.exit_code)
        self.assertIsInstance(result3.exception, SystemExit)

        # Debug mode raises an exception.
        with runner.isolated_filesystem():
            self.make_sample_files()

            cli_args4 = self.cli_args() + ['--debug', 'bootstrap']
            result4 = runner.invoke(agnostic.cli, cli_args2)

        self.assertNotEqual(0, result4.exit_code)
        self.assertIsInstance(result4.exception, ValueError)

    def test_bootstrap_migration(self):
        ''' Insert a migration into the migrations table. '''

        type_ = 'postgres'
        cursor = Mock()
        migration = 'sample_migration'
        insert_re = re.compile(r'insert', flags=re.IGNORECASE)

        agnostic._bootstrap_migration(type_, cursor, migration)

        self.assertTrue(cursor.execute.called)
        self.assertRegex(cursor.execute.call_args[0][0], insert_re)
        self.assertIn('sample_migration', cursor.execute.call_args[0][1])
        self.assertIn(
            agnostic.MIGRATION_STATUS_BOOTSTRAPPED,
            cursor.execute.call_args[0][1]
        )

    def test_bootstrap_migration_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        type_ = 'bogusdb'
        cursor = Mock()
        migration = 'sample_migration'

        with self.assertRaises(ValueError):
            agnostic._bootstrap_migration(type_, cursor, migration)

    @patch('agnostic._connect_db')
    def test_clear_schema(self, connect_db_mock):
        ''' Run SQL commands to clear a schema. '''

        config = self.config_fixture()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = [('dark_site',),('dark_user')]

        agnostic._clear_schema(config)

        self.assertTrue(connect_db_mock.called)
        self.assertTrue(cursor.execute.called)

    def test_clear_schema_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        config = self.config_fixture(type='bogusdb')

        with self.assertRaises(ValueError):
            agnostic._clear_schema(config)

    @patch('psycopg2.connect')
    def test_connect_db_psycopg2(self, connect_mock):
        ''' Connect to a postgres database with the psycopg2 driver. '''

        config = self.config_fixture()

        agnostic._connect_db(config)

        self.assertTrue(connect_mock.called)
        self.assertEqual(config.host, connect_mock.call_args[1]['host'])
        self.assertEqual(config.port, connect_mock.call_args[1]['port'])
        self.assertEqual(config.user, connect_mock.call_args[1]['user'])
        self.assertEqual(config.password, connect_mock.call_args[1]['password'])
        self.assertEqual(config.schema, connect_mock.call_args[1]['database'])

    @patch('importlib.__import__', side_effect=import_error('psycopg2'))
    def test_connect_db_psycopg2_missing(self, import_mock):
        ''' Raise exception if psycopg2 driver is not available. '''

        config = self.config_fixture(schema='myapp')

        with self.assertRaises(click.ClickException):
            agnostic._connect_db(config)

    def test_connect_db_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        config = self.config_fixture(type='bogusdb')

        with self.assertRaises(ValueError):
            agnostic._connect_db(config)

    @patch('agnostic._connect_db')
    def test_drop(self, connect_db_mock):
        ''' The "drop" CLI command with user typing 'y' on stdin. '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        drop_table_re = re.compile(r'drop\s+table', flags=re.IGNORECASE)

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['drop']
            result = runner.invoke(agnostic.cli, cli_args, input='y')

        self.assertEqual(0, result.exit_code)
        self.assertTrue(cursor.execute.called)
        self.assertRegex(cursor.execute.call_args[0][0], drop_table_re)

    @patch('agnostic._connect_db')
    def test_drop_abort(self, connect_db_mock):
        ''' The "drop" CLI command with user typing 'n' on stdin. '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        drop_table_re = re.compile(r'drop\s+table', flags=re.IGNORECASE)

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['drop']
            result = runner.invoke(agnostic.cli, cli_args, input='n')

        self.assertNotEqual(0, result.exit_code)
        self.assertFalse(cursor.execute.called)

    @patch('agnostic._connect_db')
    def test_drop_fail(self, connect_db_mock):
        ''' The "drop" CLI command should fail gracefully. '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.execute.side_effect = ValueError
        drop_table_re = re.compile(r'drop\s+table', flags=re.IGNORECASE)

        # Non-debug mode returns non-zero exit code.
        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args1 = self.cli_args() + ['drop']
            result1 = runner.invoke(agnostic.cli, cli_args1, input='y')

        self.assertNotEqual(0, result1.exit_code)
        self.assertIsInstance(result1.exception, SystemExit)

        # Debug mode raises exception.
        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args2 = self.cli_args() + ['--debug', 'drop']
            result2 = runner.invoke(agnostic.cli, cli_args2, input='y')

        self.assertNotEqual(0, result2.exit_code)
        self.assertIsInstance(result2.exception, ValueError)

    def test_get_create_table_sql(self):
        ''' Generate the SQL for creating a table. '''

        type_ = 'postgres'
        create_table_re = re.compile(r'CREATE TABLE', flags=re.IGNORECASE)

        sql = agnostic._get_create_table_sql(type_)

        self.assertRegex(sql, create_table_re)

    def test_get_create_table_sql_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        type_ = 'bogusdb'

        with self.assertRaises(ValueError):
            agnostic._get_create_table_sql(type_)

    def test_get_default_port(self):
        ''' Get the default port number for a given type of database. '''

        type_ = 'postgres'

        port = agnostic._get_default_port(type_)

        self.assertIsInstance(port, int)

    def test_get_default_port_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        type_ = 'bogusdb'

        with self.assertRaises(ValueError):
            agnostic._get_default_port(type_)

    def test_get_migration_records(self):
        ''' Get migration metadata from the migrations table. '''

        cursor = Mock()
        expected_records = (('name', 'status', None, None),)
        cursor.fetchall.return_value = expected_records

        select_re = re.compile(
            r'SELECT.*ORDER',
            flags=re.IGNORECASE | re.DOTALL
        )

        actual_records = agnostic._get_migration_records(cursor)

        self.assertTrue(cursor.execute.called)
        self.assertRegex(cursor.execute.call_args[0][0], select_re)
        self.assertIs(expected_records, actual_records)

    @patch('agnostic._get_migration_records')
    @patch('agnostic._list_migration_files')
    def test_get_pending_migrations(self, all_mock, applied_mock):
        '''
        Compute which migrations are pending given a list of applied
        migrations and a list of all migration files.
        '''

        config = self.config_fixture()
        cursor = Mock()

        applied_mock.return_value = (
            ('migration1', 'succeeded', None, None),
            ('migration2', 'succeeded', None, None),
            ('migration4', 'succeeded', None, None),
        )

        all_mock.return_value = [
            'migration1',
            'migration2',
            'migration3',
            'migration4',
            'migration5',
        ]

        expected_pending = ['migration3', 'migration5']

        actual_pending = agnostic._get_pending_migrations(config, cursor)

        self.assertEqual(expected_pending, actual_pending)

    @patch('agnostic._connect_db')
    def test_list(self, connect_db_mock):
        ''' The "list" CLI command. '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = [
            ('01/bar', 'bootstrapped', datetime.now(), datetime.now()),
            ('01/foo', 'bootstrapped', datetime.now(), datetime.now()),
            ('02_foobar', 'succeeded', datetime.now(), datetime.now()),
            ('04/bat', 'succeeded', datetime.now(), datetime.now()),
        ]

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['list']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertEqual(0, result.exit_code)
        self.assertTrue(cursor.execute.called)
        self.assertRegex(result.output, r'01/bar.*bootstrapped')
        self.assertRegex(result.output, r'01/foo.*bootstrapped')
        self.assertRegex(result.output, r'02_foobar.*succeeded')
        self.assertRegex(result.output, r'03_bazbat.*pending')
        self.assertRegex(result.output, r'04/bat.*succeeded')
        self.assertRegex(result.output, r'04/baz.*pending')

    @patch('agnostic._connect_db')
    def test_list_no_migrations(self, connect_db_mock):
        '''
        The "list" CLI command fails gracefully if there are no migrations to
        display.
        '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = []

        with runner.isolated_filesystem():
            os.mkdir('migrations')
            cli_args = self.cli_args() + ['list']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertNotEqual(0, result.exit_code)

    @patch('agnostic._connect_db')
    def test_list_invalid_status(self, connect_db_mock):
        '''
        The "list" CLI command fails gracefully if a migration has an invalid
        status.
        '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = [
            ('01/bar', 'bootstrapped', datetime.now(), datetime.now()),
            ('01/foo', 'bogus-status', datetime.now(), datetime.now()),
        ]

        # In non-debug mode, it exists with a non-zero status.
        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['list']
            result1 = runner.invoke(agnostic.cli, cli_args)

        self.assertNotEqual(0, result1.exit_code)
        self.assertIsInstance(result1.exception, SystemExit)

        # In debug mode, it raises an exception.
        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['--debug', 'list']
            result2 = runner.invoke(agnostic.cli, cli_args)

        self.assertNotEqual(0, result2.exit_code)
        self.assertIsInstance(result2.exception, ValueError)

    def test_list_migration_files(self):
        ''' List migrations on the file system in correct order. '''

        with CliRunner().isolated_filesystem():
            self.make_sample_files()
            actual_list = list(agnostic._list_migration_files('migrations'))

        # Compare this list to the list of files in self.make_sample_files().
        expected_list = [
            '01/bar',
            '01/foo',
            '02_foobar',
            '03_bazbat',
            '04/bat',
            '04/baz'
        ]

        self.assertEqual(expected_list, actual_list)

    @patch('subprocess.Popen')
    def test_load_snapshot(self, popen_mock):
        ''' Load a schema snapshot. '''

        expected_process = 'dummy_process'
        popen_mock.return_value = expected_process
        config = self.config_fixture()
        snapshot_file = Mock()

        actual_process = agnostic._load_snapshot(config, snapshot_file)

        self.assertEqual(actual_process, expected_process)

    def test_load_snapshot_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        config = self.config_fixture(type='bogusdb')
        backup_file = Mock()

        with self.assertRaises(ValueError):
            process = agnostic._load_snapshot(config, backup_file)

    @patch('subprocess.Popen')
    def test_make_snapshot(self, popen_mock):
        ''' Create a snapshot. '''

        expected_process = 'dummy_process'
        popen_mock.return_value = expected_process
        config = self.config_fixture()
        snapshot_file = Mock()

        actual_process = agnostic._make_snapshot(config, snapshot_file)

        self.assertEqual(actual_process, expected_process)

    def test_make_snapshot_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        config = self.config_fixture(type='bogusdb')
        backup_file = Mock()

        with self.assertRaises(ValueError):
            process = agnostic._make_snapshot(config, backup_file)

    @patch('agnostic._any_failed_migrations')
    @patch('agnostic._run_migrations')
    @patch('agnostic._backup')
    @patch('agnostic._connect_db')
    def test_migrate_backup(self, connect_db_mock, backup_mock, run_mig_mock,
                            any_failed_mock):
        ''' The "migrate" CLI command with --backup option. '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = [
            ('01/bar', 'bootstrapped', datetime.now(), datetime.now()),
            ('01/foo', 'bootstrapped', datetime.now(), datetime.now()),
            ('02_foobar', 'succeeded', datetime.now(), datetime.now()),
            ('04/bat', 'succeeded', datetime.now(), datetime.now()),
        ]
        process = Mock()
        process.returncode = 0
        backup_mock.return_value = process
        any_failed_mock.return_value = False

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['migrate', '--backup']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertEqual(0, result.exit_code)
        self.assertTrue(cursor.execute.called)
        self.assertTrue(backup_mock.called)
        self.assertTrue(run_mig_mock.called)
        self.assertRegex(result.output, r'run 2 migrations')

    @patch('agnostic._any_failed_migrations')
    @patch('agnostic._restore')
    @patch('agnostic._run_migrations')
    @patch('agnostic._backup')
    @patch('agnostic._connect_db')
    def test_migrate_fail(self, connect_db_mock, backup_mock, run_mig_mock,
                          restore_mock, any_failed_mock):
        '''
        If a migration fails, the "migrate" CLI command should handle it
        gracefully.
        '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = [
            ('01/bar', 'bootstrapped', datetime.now(), datetime.now()),
            ('01/foo', 'bootstrapped', datetime.now(), datetime.now()),
            ('02_foobar', 'succeeded', datetime.now(), datetime.now()),
            ('04/bat', 'succeeded', datetime.now(), datetime.now()),
        ]
        process = Mock()
        process.returncode = 0
        backup_mock.return_value = process
        restore_mock.return_value = process
        run_mig_mock.side_effect = ValueError
        any_failed_mock.return_value = False

        # In non-debug mode, should exit with non-zero code.
        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args1 = self.cli_args() + ['migrate']
            result1 = runner.invoke(agnostic.cli, cli_args1)

        self.assertNotEqual(0, result1.exit_code)
        self.assertIsInstance(result1.exception, SystemExit)

        # In debug mode, should raise an exception.
        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args2 = self.cli_args() + ['--debug', 'migrate']
            result2 = runner.invoke(agnostic.cli, cli_args2)

        self.assertNotEqual(0, result2.exit_code)
        self.assertIsInstance(result2.exception, ValueError)

    @patch('agnostic._any_failed_migrations')
    @patch('agnostic._run_migrations')
    @patch('agnostic._backup')
    @patch('agnostic._connect_db')
    def test_migrate_no_backup(self, connect_db_mock, backup_mock, run_mig_mock,
                               any_failed_mock):
        ''' The "migrate" CLI command with no --backup option. '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = [
            ('01/bar', 'bootstrapped', datetime.now(), datetime.now()),
            ('01/foo', 'bootstrapped', datetime.now(), datetime.now()),
            ('02_foobar', 'succeeded', datetime.now(), datetime.now()),
            ('04/bat', 'succeeded', datetime.now(), datetime.now()),
        ]
        process = Mock()
        process.returncode = 0
        backup_mock.return_value = process
        any_failed_mock.return_value = False

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['migrate', '--no-backup']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertEqual(0, result.exit_code)
        self.assertTrue(cursor.execute.called)
        self.assertFalse(backup_mock.called)
        self.assertTrue(run_mig_mock.called)
        self.assertRegex(result.output, r'run 2 migrations')

    @patch('agnostic._any_failed_migrations')
    @patch('agnostic._run_migrations')
    @patch('agnostic._backup')
    @patch('agnostic._connect_db')
    def test_migrate_no_migrations(self, connect_db_mock, backup_mock,
                                   run_mig_mock, any_failed_mock):
        '''
        The "migrate" CLI command should exit gracefully if there are no
        migrations to run.
        '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        cursor.fetchall.return_value = [
            ('01/bar', 'bootstrapped', datetime.now(), datetime.now()),
            ('01/foo', 'bootstrapped', datetime.now(), datetime.now()),
            ('02_foobar', 'succeeded', datetime.now(), datetime.now()),
            ('03_bazbat', 'succeeded', datetime.now(), datetime.now()),
            ('04/bat', 'succeeded', datetime.now(), datetime.now()),
            ('04/baz', 'succeeded', datetime.now(), datetime.now()),
        ]
        process = Mock()
        process.returncode = 0
        backup_mock.return_value = process
        any_failed_mock.return_value = False

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['migrate']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertNotEqual(0, result.exit_code)
        self.assertIsInstance(result.exception, SystemExit)

    @patch('agnostic._any_failed_migrations')
    @patch('agnostic._connect_db')
    def test_migrate_previously_failed(self, connect_db_mock, any_failed_mock):
        '''
        The "migrate" CLI command should exit gracefully if there are any
        previously failed migrations.
        '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        any_failed_mock.return_value = True

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['migrate']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertNotEqual(0, result.exit_code)
        self.assertIsInstance(result.exception, SystemExit)

    @patch('subprocess.Popen')
    def test_restore(self, popen_mock):
        ''' Restore from a backup. '''

        expected_process = 'dummy_process'
        popen_mock.return_value = expected_process
        config = self.config_fixture()
        snapshot_file = Mock()

        actual_process = agnostic._restore(config, snapshot_file)

        self.assertEqual(actual_process, expected_process)

    def test_restore_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        config = self.config_fixture(type='bogusdb')
        backup_file = Mock()

        with self.assertRaises(ValueError):
            process = agnostic._restore(config, backup_file)

    @unittest.skip('click.echo() is incompatible with unittest buffer')
    @patch('builtins.open')
    @patch('subprocess.Popen')
    @patch('agnostic._wait_for')
    def test_run_migrations(self, open_mock, popen_mock, wait_for_mock):
        ''' Run a given set of migrations in the given order. '''

        config = self.config_fixture()
        cursor = Mock()

        # Intentionally out of order: _run_migrations() should not reorder them.
        migrations = ['03_baz', '04_bat', '01_foo', '02_bar']

        agnostic._run_migrations(config, cursor, migrations)

        # Each migration file should be opened.
        self.assertEqual(len(migrations), open_mock.call_count)

        # Execute should be called twice for each migration.
        self.assertEqual(len(migrations) * 2, cursor.execute.call_count)

    @patch('subprocess.Popen')
    def test_run_migration_file(self, popen_mock):
        ''' Restore from a backup. '''

        expected_process = 'dummy_process'
        popen_mock.return_value = expected_process
        config = self.config_fixture()
        migration_file = '01_foo'

        actual_process = agnostic._run_migration_file(config, migration_file)

        self.assertEqual(actual_process, expected_process)

    def test_run_migration_file_unsupported(self):
        ''' Raise an exception if the database type is not supported. '''

        config = self.config_fixture(type='bogusdb')
        backup_file = Mock()

        with self.assertRaises(ValueError):
            process = agnostic._run_migration_file(config, backup_file)

    @patch('agnostic._make_snapshot')
    @patch('agnostic._migration_insert_sql')
    def test_snapshot(self, insert_sql_mock, make_snapshot_mock):
        ''' The "snapshot" CLI command. '''

        runner = CliRunner()
        process = Mock()
        process.returncode = 0
        make_snapshot_mock.return_value = process

        with runner.isolated_filesystem():
            self.make_sample_files()
            cli_args = self.cli_args() + ['snapshot', 'out.sql']
            result = runner.invoke(agnostic.cli, cli_args)

        self.assertEqual(0, result.exit_code)
        self.assertTrue(make_snapshot_mock.called)

    @patch('difflib.unified_diff')
    @patch('agnostic._run_migrations')
    @patch('agnostic._get_pending_migrations')
    @patch('agnostic._make_snapshot')
    @patch('agnostic._load_snapshot')
    @patch('agnostic._clear_schema')
    @patch('agnostic._connect_db')
    @patch('agnostic._migration_insert_sql')
    def test_test_y(self, insert_sql_mock, connect_db_mock, clear_schema_mock,
                    load_snap_mock, make_snap_mock, pending_mig_mock,
                    run_mig_mock, diff_mock):
        '''
        The "test" CLI command.

        This test is awwwwwwwful.
        '''

        runner = CliRunner()
        cursor = self.make_cursor(connect_db_mock)
        process = Mock()
        process.returncode = 0
        load_snap_mock.return_value = process
        make_snap_mock.return_value = process
        diff_mock.return_value = []

        # Should succeed with empty diff.
        with runner.isolated_filesystem():
            self.make_sample_files()

            with open('current.sql', 'w') as current:
                current.write('current')

            with open('target.sql', 'w') as target:
                target.write('target')

            cli_args2 = self.cli_args() + ['test', 'current.sql', 'target.sql']
            result1 = runner.invoke(agnostic.cli, cli_args2, input='y')

        self.assertEqual(0, result1.exit_code)
        self.assertTrue(clear_schema_mock.called)
        self.assertTrue(load_snap_mock.called)
        self.assertTrue(pending_mig_mock.called)
        self.assertTrue(run_mig_mock.called)
        self.assertTrue(make_snap_mock.called)

        # Should abort if user types 'n'.
        with runner.isolated_filesystem():
            self.make_sample_files()

            with open('current.sql', 'w') as current:
                current.write('current')

            with open('target.sql', 'w') as target:
                target.write('target')

            cli_args2 = self.cli_args() + ['test', 'current.sql', 'target.sql']
            result2 = runner.invoke(agnostic.cli, cli_args2, input='n')

        self.assertNotEqual(0, result2.exit_code)

        # Should fail with with non-empty diff.
        diff_mock.return_value = ['foo']

        with runner.isolated_filesystem():
            self.make_sample_files()

            with open('current.sql', 'w') as current:
                current.write('current')

            with open('target.sql', 'w') as target:
                target.write('target')

            cli_args3 = self.cli_args() + ['test', 'current.sql', 'target.sql']
            result3 = runner.invoke(agnostic.cli, cli_args3, input='y')

        self.assertNotEqual(0, result3.exit_code)

    def test_wait_for_process (self):
        ''' Wait for process to finish. '''

        process = Mock()
        process.returncode = 0

        agnostic._wait_for(process)

        self.assertTrue(process.wait.called)

    def test_wait_for_process_failed(self):
        ''' Raise exception if process doesn't exit cleanly. '''

        process = Mock()
        process.args = MagicMock()
        process.returncode = 1

        with self.assertRaises(click.ClickException):
            agnostic._wait_for(process)


if __name__ == '__main__':
    unittest.main(buffer=True)

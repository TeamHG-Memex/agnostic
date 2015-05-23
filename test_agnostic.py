import os
import random
import re
import unittest
from unittest.mock import MagicMock, Mock, patch

import click

import agnostic


def import_error(missing_dependency):
    ''' Simulate a missing dependency by raising an import error. '''

    def ie_helper(import_name, *args):
        if import_name == missing_dependency:
            raise ImportError()
        else:
            __import__(import_name, *args)

    return ie_helper


class MockFileSystem(object):
    ''' A quick and dirty mock for a file system. '''

    def __init__(self, tree):
        '''
        Initialize file system with list ``tree``.

        Each key of ``tree`` represents the name of a file or directory. The
        corresponding key can either be None (indicating a leaf node, i.e.
        a regular file) or a dictionary (indicating a subtree, i.e. directory).
        '''

        self.tree = tree

    def __getitem__(self, path):
        '''
        Get a mock file system entry by its path.

        This returns None if the path is a file, and it returns a dictionary
        representing the subtree if the path is a directory.
        '''

        path = path.rstrip(os.sep)

        if path == '':
            return self.tree

        path_components = list()
        head, tail = os.path.split(path)
        path_components.append(tail)

        while head != '':
            head, tail = os.path.split(head)
            path_components.append(tail)

        try:
            item = self.tree
            for path_component in reversed(path_components):
                item = item[path_component]
        except KeyError as ke:
            msg = 'No such file or directory: "%s"'
            raise FileNotFoundError(msg % path) from ke

        return item

    def listdir(self, path):
        '''
        List entries in the given directory.

        Directory entires are intentionally shuffled in a deterministic way
        to reflect the fact that os.listdir does not guarantee iteration order.
        '''

        dir_ = self[path]

        if dir_ is None:
            raise NotADirectoryError('Not a directory: "%s"' % path)
        else:
            files = list(dir_.keys())

            prng = random.Random()
            prng.seed('MockFileSystem')
            random.shuffle(files, prng.random)

            return files

    def isdir(self, path):
        ''' Return true if ``path`` is a directory. '''

        return self[path] is not None

    def isfile(self, path):
        ''' Return true if ``path`` is a regular file. '''

        return self[path] is None


class test_agnostic(unittest.TestCase):
    ''' Unit tests for Agnostic Database Migrations. '''

    def config_fixture(self, db=None, host=None, migrations_dir=None,
                       password=None, port=None, schema=None, type=None,
                       user=None):
        ''' A helper for making config objects. '''

        config = agnostic.Config

        config.db = db or Mock()
        config.host = host or 'localhost'
        config.migrations_dir = migrations_dir or 'migrations'
        config.password = password or 'mypass'
        config.port = port or 5942
        config.schema = schema or 'myapp'
        config.type = type or 'postgres'
        config.user = user or 'myuser'

        return config

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
        '''
        Run SQL commands to clear a schema.

        There's not a great test to run here -- the implementation could
        change radically. So we just make sure that it executes a command
        on the cursor.
        '''

        config = self.config_fixture()
        db = Mock()
        cursor = Mock()
        connect_db_mock.return_value = db
        db.cursor.return_value = cursor

        agnostic._clear_schema(config)

        self.assertTrue(connect_db_mock.called)
        self.assertTrue(db.cursor.called)
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

        agnostic._clear_schema(config)

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

    @patch('os.path.isdir')
    @patch('os.path.isfile')
    @patch('os.listdir')
    def test_list_migration_files(self, listdir_mock, isfile_mock, isdir_mock):
        ''' List migrations on the file system in correct order. '''

        file_system = MockFileSystem({
            'migrations': {
                '01': {'foo.sql': None, 'bar.sql': None},
                '02_foobar.sql': None,
                '03_bazbat.sql': None,
                '04': {'baz.sql': None, 'bat.sql': None},
            }
        })

        expected_list = [
            '01/bar',
            '01/foo',
            '02_foobar',
            '03_bazbat',
            '04/bat',
            '04/baz'
        ]

        listdir_mock.side_effect = file_system.listdir
        isfile_mock.side_effect = file_system.isfile
        isdir_mock.side_effect = file_system.isdir

        actual_list = list(agnostic._list_migration_files('migrations'))

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

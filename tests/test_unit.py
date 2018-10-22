import logging
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import agnostic
import agnostic.cli
from agnostic.mysql import MysqlBackend
from agnostic.postgres import PostgresBackend
from agnostic.sqlite import SqlLiteBackend


logging.basicConfig()


class TestUnit(unittest.TestCase):
    ''' Unit tests for Agnostic '''

    def touch_file(self, name):
        with open(name, 'w'):
            pass

    def test_list_migrations(self):
        tempdir = tempfile.mkdtemp(dir='/tmp')
        os.mkdir(tempdir + '/01')
        os.mkdir(tempdir + '/02')
        self.touch_file(tempdir + '/01/2_more_stuff.sql')
        self.touch_file(tempdir + '/02/1_do_stuff.sql')
        self.touch_file(tempdir + '/01/@_sort_bottom.sql')
        self.touch_file(tempdir + '/02/!_sort_top.sql')
        migrations = agnostic.cli._list_migration_files(tempdir)
        self.assertEqual(migrations, [
            '01/2_more_stuff',
            '01/@_sort_bottom',
            '02/!_sort_top',
            '02/1_do_stuff',
        ])
        shutil.rmtree(tempdir)

    def test_invalid_migration_status(self):
        with self.assertRaises(ValueError):
            agnostic.Migration('1-my-name', b'status-code')

    def test_invalid_migration_datetime(self):
        with self.assertRaises(ValueError):
            m = agnostic.Migration('1-my-name', 'bootstrapped',
                started_at=b'2018-01-01 12:00:00')

    def test_mysql_backend(self):
        be = agnostic.create_backend('mysql', 'localhost', None, 'root',
            'password', 'testdb', None)
        self.assertIsInstance(be, MysqlBackend)
        self.assertEqual(be.location, 'database [testdb]')

    def test_mysql_backend_schema_not_allowed(self):
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('mysql', 'localhost', None,
                'root', 'password', 'testdb', 'testschema')

    def test_mysql_backend_required_arguments(self):
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('mysql', 'localhost', None,
                None, 'password', 'testdb', None)
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('mysql', 'localhost', None,
                'root', 'password', None, None)

    @patch('agnostic.getpass', side_effect=lambda x: None)
    def test_mysql_backend_no_pass(self, mock_getpass):
        be = agnostic.create_backend('mysql', 'localhost', None, 'root',
            None, 'testdb', None)
        mock_getpass.assert_called_with('Enter password for "root" on "testdb":')

    @patch('agnostic.mysql.subprocess')
    def test_mysql_backup_with_port(self, mock_subprocess):
        be = agnostic.create_backend('mysql', 'localhost', 3307, 'root',
            'password', 'testdb', None)
        be.backup_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['mysqldump', '-h', 'localhost', '-u',
            'root', '-P', '3307', 'testdb'])
        self.assertEqual(args[1]['env'], {'MYSQL_PWD': 'password'})

    @patch('agnostic.mysql.pymysql')
    def test_mysql_connect_with_port(self, mock_pymysql):
        be = agnostic.create_backend('mysql', 'localhost', 3307, 'root',
            'password', 'testdb', None)
        be.connect_db()
        self.assertTrue(mock_pymysql.connect.called)
        self.assertEqual(mock_pymysql.connect.call_args[1], {
            'host': 'localhost',
            'user': 'root',
            'password': 'password',
            'database': 'testdb',
            'autocommit': True,
            'port': 3307,
        })

    @patch('agnostic.mysql.subprocess')
    def test_mysql_restore_with_port(self, mock_subprocess):
        be = agnostic.create_backend('mysql', 'localhost', 3307, 'root',
            'password', 'testdb', None)
        be.restore_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['mysql', '-h', 'localhost', '-u',
            'root', '-P', '3307', 'testdb'])
        self.assertEqual(args[1]['env'], {'MYSQL_PWD': 'password'})

    @patch('agnostic.mysql.subprocess')
    def test_mysql_snapshot_with_port(self, mock_subprocess):
        be = agnostic.create_backend('mysql', 'localhost', 3307, 'root',
            'password', 'testdb', None)
        be.snapshot_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['mysqldump', '-h', 'localhost', '-u',
            'root', '--no-create-db', '--no-data', '--compact', '-P', '3307',
            'testdb'])
        self.assertEqual(args[1]['env'], {'MYSQL_PWD': 'password'})

    def test_postgres_backend(self):
        be = agnostic.create_backend('postgres', 'localhost', None, 'root',
            'password', 'testdb', None)
        self.assertIsInstance(be, PostgresBackend)
        self.assertEqual(be.location, 'database [testdb]')

    def test_postgres_backend_with_schema(self):
        be = agnostic.create_backend('postgres', 'localhost', None, 'root',
            'password', 'testdb', '"$user",public')
        self.assertIsInstance(be, PostgresBackend)
        self.assertEqual(be.location,
            'database [testdb schema="$user",public]')
        self.assertEqual(be.get_schema_command(),
            'SET search_path = "$user",public;\n')

    def test_postgres_backend_required_arguments(self):
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('postgres', 'localhost', None,
                None, 'password', 'testdb', None)
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('postgres', 'localhost', None,
                'root', 'password', None, None)

    @patch('agnostic.getpass', side_effect=lambda x: None)
    def test_postgres_backend_no_pass(self, mock_getpass):
        be = agnostic.create_backend('postgres', 'localhost', None, 'root',
            None, 'testdb', None)
        mock_getpass.assert_called_with('Enter password for "root" on "testdb":')

    @patch('agnostic.postgres.subprocess')
    def test_postgres_backup_with_port(self, mock_subprocess):
        be = agnostic.create_backend('postgres', 'localhost', 5433, 'root',
            'password', 'testdb', None)
        be.backup_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['pg_dump', '-h', 'localhost', '-U',
            'root', '-p', '5433', 'testdb'])
        self.assertEqual(args[1]['env'], {'PGPASSWORD': 'password'})

    @patch('agnostic.postgres.pg8000')
    def test_postgres_connect_with_port(self, mock_pymysql):
        be = agnostic.create_backend('postgres', 'localhost', 5433, 'root',
            'password', 'testdb', None)
        be.connect_db()
        self.assertTrue(mock_pymysql.connect.called)
        self.assertEqual(mock_pymysql.connect.call_args[1], {
            'host': 'localhost',
            'user': 'root',
            'password': 'password',
            'database': 'testdb',
            'port': 5433,
        })

    @patch('agnostic.postgres.subprocess')
    def test_postgres_restore_with_port(self, mock_subprocess):
        be = agnostic.create_backend('postgres', 'localhost', 5433, 'root',
            'password', 'testdb', None)
        be.restore_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['psql', '-h', 'localhost', '-U',
            'root', '-v', 'ON_ERROR_STOP=1', '-p', '5433', 'testdb'])
        self.assertEqual(args[1]['env'], {'PGPASSWORD': 'password'})

    @patch('agnostic.postgres.subprocess')
    def test_postgres_snapshot_with_port(self, mock_subprocess):
        be = agnostic.create_backend('postgres', 'localhost', 5433, 'root',
            'password', 'testdb', None)
        be.snapshot_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['pg_dump', '-h', 'localhost', '-U',
            'root', '-s', '-x', '-O', '--no-tablespaces', '-p', '5433',
            'testdb'])
        self.assertEqual(args[1]['env'], {'PGPASSWORD': 'password'})

    @patch('agnostic.postgres.subprocess')
    def test_postgres_backup_with_schema(self, mock_subprocess):
        be = agnostic.create_backend('postgres', 'localhost', None, 'root',
            'password', 'testdb', 'testschema')
        be.backup_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['pg_dump', '-h', 'localhost', '-U',
            'root', '-n', 'testschema', 'testdb'])
        self.assertEqual(args[1]['env'], {'PGPASSWORD': 'password'})

    @patch('agnostic.postgres.pg8000')
    def test_postgres_connect_with_schema(self, mock_pymysql):
        be = agnostic.create_backend('postgres', 'localhost', None, 'root',
            'password', 'testdb', 'testschema')
        db = be.connect_db()
        self.assertTrue(mock_pymysql.connect.called)
        self.assertEqual(mock_pymysql.connect.call_args[1], {
            'host': 'localhost',
            'user': 'root',
            'password': 'password',
            'database': 'testdb',
        })
        cursor = db.cursor.return_value
        cursor.execute.assert_called_with("SET SCHEMA 'testschema'")

    @patch('agnostic.postgres.subprocess')
    def test_postgres_snapshot_with_schema(self, mock_subprocess):
        be = agnostic.create_backend('postgres', 'localhost', None, 'root',
            'password', 'testdb', '"$user",public')
        be.snapshot_db('test-file')
        self.assertTrue(mock_subprocess.Popen.called)
        args = mock_subprocess.Popen.call_args
        self.assertEqual(args[0][0], ['pg_dump', '-h', 'localhost', '-U',
            'root', '-s', '-x', '-O', '--no-tablespaces', '-n', 'root', '-n',
            'public', 'testdb'])
        self.assertEqual(args[1]['env'], {'PGPASSWORD': 'password'})

    def test_postgres_clear_db_with_schema(self):
        be = agnostic.create_backend('postgres', 'localhost', None, 'root',
            'password', 'testdb', 'schema1,public')
        mock_cursor = MagicMock()
        be.clear_db(mock_cursor)
        self.assertTrue(mock_cursor.execute.called)
        mock_cursor.execute.assert_any_call(
            'DROP SCHEMA IF EXISTS schema1 CASCADE')

    def test_sqlite_backend(self):
        be = agnostic.create_backend('sqlite', None, None, None, None,
            'test.db', None)
        self.assertIsInstance(be, SqlLiteBackend)
        self.assertEqual(be.location, 'database [test.db]')

    def test_sqlite_backend_arguments_not_allowed(self):
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('sqlite', 'localhost', None, None,
                None, 'test.db', None)
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('sqlite', None, None, 'root',
                None, 'test.db', None)
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('sqlite', None, None, None,
                'password', 'test.db', None)
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('sqlite', None, None, None, None,
                'test.db', 'testschema')

    def test_sqlite_backend_required_arguments(self):
        with self.assertRaises(RuntimeError):
            be = agnostic.create_backend('sqlite', None, None,
                None, None, None, None)

    def test_invalid_backend(self):
        with self.assertRaises(ValueError):
            be = agnostic.create_backend('bogusdb', 'localhost', None, 'root',
                'password', 'testdb', None)

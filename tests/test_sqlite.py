import os
import shutil
import sqlite3
import tempfile
import unittest

from tests.abstract import AbstractDatabaseTest


class TestSqlLite(AbstractDatabaseTest, unittest.TestCase):
    ''' Integration tests for SQLite '''

    def __init__(self, *args, **kwargs):
        ''' Override super class: set param style. '''
        super().__init__(*args, **kwargs)
        self._param = '?'

    @property
    def db_type(self):
        ''' The database type as a string. '''
        return 'sqlite'

    @property
    def default_db(self):
        ''' We don't drop databases in this class, so this isn't used.. '''
        raise NotImplemented()

    def connect_db(self, user, password, database):
        ''' Return a connection to the specified database. '''

        db = sqlite3.connect(database)
        db.isolation_level = None # Equivalent to autocommit
        return db

    def get_credentials_from_env(self):
        '''
        Override super class: SQLite does not use credentials, so we stub this
        out.
        '''
        return None, None

    def get_base_command(self):
        ''' Override super class: omit non-SQLite options. '''
        command = [
            '-t', self.db_type,
            '-d', self._test_db,
        ]

        return command

    def setUp(self):
        ''' Override super class: don't need to drop or create database, just
        create a temp file and delete it later. '''
        _, self._test_db = tempfile.mkstemp(suffix='.db')

    def tearDown(self):
        ''' Remove temporary DB file. '''
        # os.unlink(self._test_db)

    def table_columns(self, cursor, database, table_name):
        ''' Return a list of columns in the specified table. '''
        sql = "pragma table_info('{}')".format(table_name)
        cursor.execute(sql)
        columns = [row[1] for row in cursor.fetchall()]
        return columns

    def table_exists(self, cursor, database, table_name):
        ''' Return true if the specified table exists. '''

        table_query = '''
            SELECT COUNT(*)
              FROM sqlite_master
             WHERE name = ?
        '''

        cursor.execute(table_query, (table_name,))
        return cursor.fetchone()[0] == 1

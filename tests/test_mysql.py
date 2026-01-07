import os
import unittest

import pymysql

from tests.abstract import AbstractDatabaseTest


class TestMysql(AbstractDatabaseTest, unittest.TestCase):
    ''' Integration tests for MySQL '''

    # Note that MySQL uses "schema" and "database" interchangeably, which leads
    # to some unintuitive code in this test suite.

    @property
    def db_type(self):
        ''' The database type as a string. '''
        return 'mysql'

    @property
    def default_db(self):
        ''' The database to connect when dropping/creating a test database. '''
        return 'mysql'

    def connect_db(self, user, password, database):
        ''' Return a connection to the specified database. '''

        connect_args = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'user': user,
            'password': password,
            'database': database,
            'autocommit': True
        }

        port = os.getenv('MYSQL_PORT', None)

        if port is not None:
            connect_args['port'] = int(port)

        return pymysql.connect(**connect_args)

    def table_columns(self, cursor, database, table_name):
        ''' Return a list of columns in the specified table. '''

        sql = '''
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = %s AND table_name = %s
          ORDER BY ordinal_position
        '''

        cursor.execute(sql, (database, table_name))
        return [row[0] for row in cursor.fetchall()]

    def table_exists(self, cursor, database, table_name):
        ''' Return true if the specified table exists. '''

        table_query = '''
            SELECT COUNT(*)
              FROM information_schema.tables
             WHERE table_schema = %s AND table_name = %s
        '''

        cursor.execute(table_query, (database, table_name))
        return cursor.fetchone()[0] == 1

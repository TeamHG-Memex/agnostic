import os
import unittest

import pg8000

from tests.abstract import AbstractDatabaseTest


class TestPostgreSql(AbstractDatabaseTest, unittest.TestCase):
    ''' Integration tests for PostgreSQL '''

    @property
    def db_type(self):
        ''' The database type as a string. '''
        return 'postgres'

    @property
    def default_db(self):
        ''' The database to connect when dropping/creating a test database. '''
        return 'postgres'

    def connect_db(self, user, password, database):
        ''' Return a connection to the specified database. '''

        connect_args = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'user': user,
            'password': password,
            'database': database,
            'timeout': 1,
        }

        try:
            connect_args['port'] = os.environ['POSTGRES_PORT']
        except KeyError:
            pass

        db = pg8000.connect(**connect_args)
        db.autocommit = True
        return db

    def table_columns(self, cursor, database, table_name):
        ''' Return a list of columns in the specified table. '''

        sql = '''
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = %s
          ORDER BY ordinal_position
        '''

        cursor.execute(sql, (table_name,))
        return [row[0] for row in cursor.fetchall()]

    def table_exists(self, cursor, database, table_name):
        ''' Return true if the specified table exists. '''

        table_query = '''
            SELECT COUNT(*)
              FROM information_schema.tables
             WHERE table_name = %s
        '''

        cursor.execute(table_query, (table_name,))
        return cursor.fetchone()[0] == 1

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
from tests.abstract import AbstractDatabaseTest


class TestPostgreSql(AbstractDatabaseTest, unittest.TestCase):
    '''
    Integration tests for Agnostic Database Migrations & PostgreSQL.
    '''

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

        db = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', None),
            user=user,
            password=password,
            database=database
        )

        db.autocommit = True
        return db

    def table_columns(self, cursor, table_name):
        ''' Return a list of columns in the specified table. '''

        sql = '''
            SELECT column_name
              FROM information_schema.columns
             WHERE table_name = %s
          ORDER BY ordinal_position
        '''

        cursor.execute(sql, (table_name,))
        return [row[0] for row in cursor.fetchall()]

    def table_exists(self, cursor, table_name):
        ''' Return true if the specified table exists. '''

        table_query = '''
            SELECT COUNT(*)
              FROM pg_tables
             WHERE tablename LIKE %s
        '''

        cursor.execute(table_query, (table_name,))
        return cursor.fetchone()[0] == 1

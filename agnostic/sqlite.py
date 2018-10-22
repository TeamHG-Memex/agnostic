import shutil
import sqlite3
import subprocess

from agnostic import AbstractBackend


class SqlLiteBackend(AbstractBackend):
    ''' Support for SQLite. '''

    def __init__(self, *args):
        super().__init__(*args)
        self._param = '?'
        self._now_fn = 'datetime()'

    def backup_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will backup the database to the
        ``backup_file`` handle.
        '''

        process = subprocess.Popen(
            ['sqlite3', self._database, '.dump'],
            stdout=backup_file,
            stderr=subprocess.PIPE
        )

        return process

    def clear_db(self, cursor):
        ''' Remove all objects from the database. '''

        # Drop tables.
        cursor.execute('PRAGMA foreign_keys = OFF')
        cursor.execute("SELECT name from sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute('DROP TABLE {}'.format(table))

    def connect_db(self):
        ''' Connect to PostgreSQL. '''
        db = sqlite3.connect(self._database)
        db.isolation_level = None # Equivalent to autocommit
        return db

    def restore_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will restore the database from the
        ``backup_file`` handle.

        In SQLite we can easily backup/restore by copying the entire database
        file, so we immediately close the open file and run ``cp`` instead.
        '''

        process = subprocess.Popen(
            ['sqlite3', self._database],
            stdin= backup_file,
            stderr=subprocess.PIPE
        )

        return process

    def snapshot_db(self, snapshot_file):
        '''
        Return a ``Popen`` instance that writes a snapshot to ``snapshot_file``.
        '''

        process = subprocess.Popen(
            ['sqlite3', self._database, '.schema'],
            stdout=snapshot_file,
            stderr=subprocess.PIPE
        )

        return process

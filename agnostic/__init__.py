from abc import ABCMeta, abstractmethod
from datetime import datetime
from enum import Enum
from getpass import getpass


MigrationStatus = Enum(
    'MigrationStatus',
    'bootstrapped pending succeeded failed'
)


# Different databases treat timestamp columns differently, e.g. MySQL will
# automatically coerce `null` to `now()``! To be defensive, we explicitly
# include the `NULL DEFAULT NULL` for nullable fields, even though it might
# be redundant in ANSI SQL.
MIGRATION_TABLE_SQL = '''
    CREATE TABLE agnostic_migrations (
        name VARCHAR(255) PRIMARY KEY,
        status VARCHAR(255) NULL DEFAULT NULL,
        started_at TIMESTAMP NULL DEFAULT NULL,
        completed_at TIMESTAMP NULL DEFAULT NULL
    )
'''


class Migration():
    ''' Data model for migration metadata. '''

    def __init__(self, name, status, started_at=None, completed_at=None):
        '''
        Constructor.

        The constructor takes arguments in the same order as the table's
        columns, so it can be instantiated like ``Migration(*row)``, where
        ``row`` is a row from the table.
        '''

        self.name = name

        if isinstance(status, MigrationStatus):
            self.status = status
        elif isinstance(status, str):
            self.status = MigrationStatus[status]
        else:
            msg = '`status` must be an instance of str or MigrationStatus.'
            raise ValueError(msg)

        self.started_at = self.parse_datetime(started_at)
        self.completed_at = self.parse_datetime(completed_at)

    def parse_datetime(self, dt):
        if dt is None:
            return None
        elif isinstance(dt, datetime):
            return dt
        elif isinstance(dt, str):
            try:
                # ISO SQL date:
                return datetime.strptime(dt, '%Y-%m-%d %H:%M:%S.%f')
            except:
                # Try again without fractional seconds:
                return datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        else:
            msg = '`{}` must be None or an instance of str or datetime.'
            raise ValueError(repr(dt))

    # def to_sql(self): TODO DELETE
    #     ''' Serialize this migration metadata to a tuple of SQL strings. '''

    #     return (
    #         self.name,
    #         self.status.name,
    #         self.started_at.strftime(Migration.SQL_DATE_FORMAT),
    #         self.completed_at.strftime(Migration.SQL_DATE_FORMAT),
    #     )


def create_backend(db_type, host, port, user, password, database, schema):
    '''
    Return a new backend instance.
    '''
    def askpass(user, db):
        return getpass('Enter password for "{}" on "{}":'.format(user, db))

    if db_type == 'mysql':
        if schema is not None:
            raise RuntimeError('MySQL does not support schemas.')
        if user is None or database is None:
            raise RuntimeError('MySQL requires user and database arguments.')
        host = host or 'localhost'
        if password is None:
            password = askpass(user, database)
        try:
            from agnostic.mysql import MysqlBackend
        except ImportError as ie: # pragma: no cover
            if ie.name == 'pymysql':
                raise RuntimeError('The `pymysql` module is required for '
                    'MySQL.')
            else:
                raise
        return MysqlBackend(host, port, user, password, database, schema)

    elif db_type == 'postgres':
        if user is None or database is None:
            raise RuntimeError('PostgreSQL requires user and database '
                'arguments.')
        host = host or 'localhost'
        password = password or askpass(user, database)
        try:
            from agnostic.postgres import PostgresBackend
        except ImportError as ie: # pragma: no cover
            if ie.name == 'pg8000':
                raise RuntimeError('The `pg8000` module is required for '
                    ' Postgres.')
            else:
                raise
        return PostgresBackend(host, port, user, password, database, schema)

    elif db_type == 'sqlite':
        if (host is not None or port is not None or user is not None or
            password is not None or schema is not None):
            raise RuntimeError('SQLite does not allow host, port, user, '
                'password, or schema arguments.')
        if database is None:
            raise RuntimeError('SQLite requires a database argument.')
        from agnostic.sqlite import SqlLiteBackend
        return SqlLiteBackend(host, port, user, password, database, schema)

    else:
        raise ValueError('Invalid database type: "{}"'.format(db_type))


class AbstractBackend(metaclass=ABCMeta):
    ''' Base class for Agnostic backends. '''

    @property
    def location(self):
        schema = '' if self._schema is None else ' schema={}'.format(
            self._schema)
        location = 'database [{}{}]'.format(self._database, schema)
        return location

    def __init__(self, host, port, user, password, database, schema):
        ''' Constructor. '''

        self._param = '%s'
        self._now_fn = 'NOW()'
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._schema = schema

    @abstractmethod
    def backup_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will backup the database to the
        ``backup_file`` handle.
        '''

    @abstractmethod
    def clear_db(self, cursor):
        ''' Remove all objects from the database. '''

    @abstractmethod
    def connect_db(self):
        ''' Return a database connection. '''

    @abstractmethod
    def get_schema_command(self):
        ''' Get a command for setting the current schema. '''

    @abstractmethod
    def restore_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will restore the database from the
        ``backup_file`` handle.

        This should work both for snapshots and backups.
        '''

    @abstractmethod
    def snapshot_db(self, snapshot_file):
        '''
        Return a ``Popen`` instance that writes a snapshot to ``outfile``.

        The snapshot must contain just the database structure (i.e. no data),
        produced in a deterministic way such that the same database structure
        dumped on a different host or at a different time would produce a
        byte-for-byte identical snapshot.

        Stderr should be connected to a pipe so that the caller can read error
        messages, if any.
        '''

    def bootstrap_migration(self, cursor, migration_name):
        '''
        Insert a row into the migration table with the 'bootstrapped' status.
        '''
        print('BOOTSTRAP {}'.format(migration_name))
        sql = 'INSERT INTO agnostic_migrations VALUES ({}, {}, {}, {})'.format(
            self._param, self._param, self._now_fn, self._now_fn)
        print(sql)
        cursor.execute(sql, (migration_name, MigrationStatus.bootstrapped.name))

    def create_migrations_table(self, cursor):
        ''' Create the migrations table. '''

        cursor.execute(MIGRATION_TABLE_SQL)

    def drop_migrations_table(self, cursor):
        ''' Drop the migrations table. '''

        cursor.execute('DROP TABLE agnostic_migrations')

    def get_migration_records(self, cursor):
        ''' Get migrations metadata from the database. '''

        query = '''
            SELECT name, status, started_at, completed_at
              FROM agnostic_migrations
          ORDER BY started_at, name
        '''

        cursor.execute(query)
        return [Migration(*row) for row in cursor.fetchall()]

    def get_schema_command(self):
        ''' Return a command that will set schema. This is a no-op by default
        because most backends don't support schemas. '''

        return 'SELECT 1;\n'

    def has_failed_migrations(self, cursor):
        '''
        Return True if there are any failed migrations, or False otherwise.
        '''

        query = '''
            SELECT COUNT(*) FROM agnostic_migrations
            WHERE status LIKE {};
        '''.format(self._param)

        cursor.execute(query, (MigrationStatus.failed.name,))
        return cursor.fetchone()[0] != 0

    def migration_started(self, cursor, migration):
        '''
        Update migration metadata to indicate that the specified migration
        has been started.

        The migration is marked as 'failed' so that if it does, in fact, fail,
        no further updates are necessary. If the migration succeeds, then the
        metadata is updated (in ``migration_succeeded()``) to reflect that.
        '''

        sql = '''
            INSERT INTO agnostic_migrations (name, status, started_at)
            VALUES ({}, {}, {})
        '''.format(self._param, self._param, self._now_fn)

        cursor.execute(sql, [migration.name, MigrationStatus.failed.name])

    def migration_succeeded(self, cursor, migration):
        '''
        Update migration metadata to indicate that the specified migration
        finished successfully.
        '''

        sql = '''
            UPDATE agnostic_migrations
               SET status = {}, completed_at = {}
             WHERE name = {}
        '''.format(self._param, self._now_fn, self._param)

        cursor.execute(sql, [MigrationStatus.succeeded.name, migration.name])

    def write_migration_inserts(self, cursor, outfile):
        ''' Write SQL for inserting migration metadata to `outfile`. '''

        outfile.write(self.get_schema_command())
        insert_sql = (
            "INSERT INTO agnostic_migrations VALUES "
            "('{}', '{}', {}, {});\n"
        )

        for migration in self.get_migration_records(cursor):
            outfile.write(insert_sql.format(migration.name,
                MigrationStatus.succeeded.name, self._now_fn, self._now_fn))

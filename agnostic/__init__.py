from abc import ABCMeta, abstractmethod
from datetime import datetime
from enum import Enum


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

    SQL_DATE_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

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

        def parse_date(name, date):
            if date is None:
                return None
            elif isinstance(date, datetime):
                return date
            elif isinstance(date, str):
                return datetime.strptime(date, Migration.SQL_DATE_FORMAT)
            else:
                msg = '`{}` must be None or an instance of str or datetime.'
                raise ValueError(msg.format(name))

        self.started_at = parse_date('started_at', started_at)
        self.completed_at = parse_date('completed_at', completed_at)

    def to_sql(self):
        ''' Serialize this migration metadata to a tuple of SQL strings. '''

        return (
            self.name,
            self.status.name,
            self.started_at.strftime(Migration.SQL_DATE_FORMAT),
            self.completed_at.strftime(Migration.SQL_DATE_FORMAT),
        )


def create_backend(db_type, host, port, user, password, database, schema):
    '''
    Return a new backend instance.
    '''

    if db_type == 'mysql':
        if schema is not None:
            raise RuntimeError('MySQL does not support schemas.')

        try:
            from agnostic.mysql import MysqlBackend
        except ImportError as ie:
            if ie.name == 'pymysql':
                msg = 'The `pymysql` module is required for MySQL.'
                raise RuntimeError(msg)
            else:
                raise
        return MysqlBackend(host, port, user, password, database, schema)

    elif db_type == 'postgres':
        try:
            from agnostic.postgres import PostgresBackend
        except ImportError as ie:
            if ie.name == 'pg8000':
                msg = 'The `pg8000` module is required for Postgres.'
                raise RuntimeError(msg)
            else:
                raise
        return PostgresBackend(host, port, user, password, database, schema)

    else:
        raise ValueError('Invalid database type: "{}"'.format(db_type))


class AbstractBackend(metaclass=ABCMeta):
    ''' Base class for Agnostic backends. '''

    @property
    def location(self):
        location = 'database "{}"'.format(self._database)

        if self._schema is not None:
            location += ' (schema: {})'.format(self._schema)

        return location

    def __init__(self, host, port, user, password, database, schema):
        ''' Constructor. '''

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
    def restore_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will restore the database from the
        ``backup_file`` handle.

        This should work both for snapshots and backups.
        '''

    @abstractmethod
    def set_schema(self, cursor):
        ''' Set the current schema for the specified cursor. '''

    @abstractmethod
    def snapshot_db(self, snapshot_file):
        '''
        Return a ``Popen`` instance that writes a snapshot to ``outfile``.

        The snapshot must contain just the schema (i.e. no data), produced in a
        deterministic way such that the same schema dumped on a different host
        or at a different time would produce a byte-for-byte identical snapshot.

        Stderr should be connected to a pipe so that the caller can read error
        messages, if any.
        '''

    def bootstrap_migration(self, cursor, migration_name):
        '''
        Insert a row into the migration table with the 'bootstrapped' status.
        '''

        sql = 'INSERT INTO agnostic_migrations VALUES (%s, %s, NOW(), NOW())'
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

    def has_failed_migrations(self, cursor):
        '''
        Return True if there are any failed migrations, or False otherwise.
        '''

        query = '''
            SELECT COUNT(*) FROM agnostic_migrations
            WHERE status LIKE %s;
        '''

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
            VALUES (%s, %s, NOW())
        '''

        cursor.execute(sql, [migration.name, MigrationStatus.failed.name])

    def migration_succeeded(self, cursor, migration):
        '''
        Update migration metadata to indicate that the specified migration
        finished successfully.
        '''

        sql = '''
            UPDATE agnostic_migrations
               SET status = %s, completed_at = NOW()
             WHERE name = %s
        '''

        cursor.execute(sql, [MigrationStatus.succeeded.name, migration.name])

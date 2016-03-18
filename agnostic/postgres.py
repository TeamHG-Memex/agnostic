import subprocess

import pg8000

from agnostic import AbstractBackend


class PostgresBackend(AbstractBackend):
    ''' Support for PostgreSQL. '''

    def backup_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will backup the database to the
        ``backup_file`` handle.
        '''

        env = {'PGPASSWORD': self._password}

        command = [
            'pg_dump',
            '-h', self._host,
            '-U', self._user,
        ]

        if self._port is not None:
            command.append('-p')
            command.append(str(self._port))

        for schema in self._split_schema():
            command.append('-n')
            command.append(schema)

        command.append(self._database)

        process = subprocess.Popen(
            command,
            env=env,
            stdout=backup_file,
            stderr=subprocess.PIPE
        )

        return process

    def clear_db(self, cursor):
        ''' Remove all objects from the database. '''

        # Drop tables.
        cursor.execute('''
            SELECT schemaname, tablename FROM pg_tables
             WHERE tableowner = %s
               AND schemaname != 'pg_catalog'
               AND schemaname != 'information_schema'
        ''', (self._user,))

        tables = ['"{}"."{}"'.format(r[0], r[1]) for r in cursor.fetchall()]

        if len(tables) > 0:
            sql = 'DROP TABLE {} CASCADE'.format(', '.join(tables))
            cursor.execute(sql)

        # Drop sequences.
        cursor.execute('''
            SELECT relname FROM pg_class
             WHERE relkind = 'S'
        ''')

        sequences = ['"{}"'.format(row[0]) for row in cursor.fetchall()]

        if len(sequences) > 0:
            sql = 'DROP SEQUENCE {} CASCADE'.format(','.join(sequences))
            cursor.execute(sql)

        # Drop custom types, e.g. ENUM types.
        cursor.execute('''
            SELECT typname FROM pg_type
             WHERE typtype = 'e'
        ''')

        types = ['"{}"'.format(row[0]) for row in cursor.fetchall()]

        if len(types) > 0:
            sql = 'DROP TYPE {} CASCADE'.format(','.join(types))
            cursor.execute(sql)

        # Drop schema objects.
        for schema in self._split_schema():
            if schema != 'public':
                sql = 'DROP SCHEMA IF EXISTS %s CASCADE'.format(schema)
                cursor.execute(sql)

    def connect_db(self):
        ''' Connect to PostgreSQL. '''

        connect_args = {
            'host': self._host,
            'user': self._user,
            'password': self._password,
            'database': self._database,
        }

        if self._port is not None:
            connect_args['port'] = self._port

        db = pg8000.connect(**connect_args)
        db.autocommit = True
        return db

    def restore_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will restore the database from the
        ``backup_file`` handle.
        '''

        env = {'PGPASSWORD': self._password}

        command = [
            'psql',
            '-h', self._host,
            '-U', self._user,
            '-v', 'ON_ERROR_STOP=1', # Fail fast if an error occurs.
        ]

        if self._port is not None:
            command.append('-p')
            command.append(str(self._port))

        command.append(self._database)

        process = subprocess.Popen(
            command,
            env=env,
            stdin=backup_file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        return process

    def set_schema(self, cursor):
        ''' Return a command that will set the current schema. '''

        if self._schema is not None:
            cursor.execute('SET search_path TO {};\n'.format(self._schema))

    def snapshot_db(self, snapshot_file):
        '''
        Return a ``Popen`` instance that writes a snapshot to ``snapshot_file``.
        '''

        env = {'PGPASSWORD': self._password}

        command = [
            'pg_dump',
            '-h', self._host,
            '-U', self._user,
            '-s', # dump schema only
            '-x', # don't dump grant/revoke statements
            '-O', # don't dump ownership commands
            '--no-tablespaces',
        ]

        if self._port is not None:
            command.append('-p')
            command.append(str(self._port))

        if self._schema is not None:
            for schema in self._split_schema():
                command.extend(('-n', schema))

        command.append(self._database)

        process = subprocess.Popen(
            command,
            env=env,
            stdout=snapshot_file,
            stderr=subprocess.PIPE
        )

        return process

    def _split_schema(self):
        '''
        Split schema string into separate schema names.

        PostgreSQL allows specifying the schema name as a search path that
        look for objects in more than one schema. This method breaks that
        search path into individual schema names.

        It also replaces the special schema name ``"$user"`` (quotes included)
        with the current username, mimicking the ``SET SEARCH PATH TO ...``
        behavior in PostgreSQL.
        '''

        schemas = list()

        if self._schema is not None:
            for schema in map(str.strip, self._schema.split(',')):
                if schema == '"$user"':
                    schemas.append(self._user)
                else:
                    schemas.append(schema)

        return schemas

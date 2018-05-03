import subprocess

import snowflake.connector

from agnostic import AbstractBackend


class SnowflakeBackend(AbstractBackend):
    ''' Support for Snowflake. '''

    def connect_db(self):
        ''' Connect to Snowflake. '''

        connect_args = {
            'user': self._user,
            'password': self._password,
            'account': self._host,
            'database': self._database,
            'autocommit': True,
            'schema': self._schema
        }

        if self._port is not None:
            connect_args['port'] = self._port

        return snowflake.connector.connect(**connect_args)

    def set_schema(self, cursor):
        ''' Return a command that will set the current schema. '''

        if self._schema is not None:
            cursor.execute('USE {}.{};\n'.format(self._database, self._schema))
        else:
            cursor.execute('USE {};\n'.format(self._database))

    def backup_db(self, backup_file):
        raise('Snowflake cannot backup DB')

    def clear_db(self, cursor):
        raise('Snowflake cannot clear DB')

    def restore_db(self, backup_file):
        raise('Snowflake cannot restore DB')

    def snapshot_db(self, snapshot_file):
        raise('Snowflake cannot snapshot DB')

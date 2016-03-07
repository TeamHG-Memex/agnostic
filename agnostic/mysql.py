import subprocess

import pymysql

from agnostic import AbstractBackend


class MysqlBackend(AbstractBackend):
    ''' Support for MySQL. '''

    def backup_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will backup the database to the
        ``backup_file`` handle.
        '''

        env = {'MYSQL_PWD': self._password}

        command = [
            'mysqldump',
            '-h', self._host,
            '-u', self._user,
        ]

        if self._port is not None:
            command.append('-P')
            command.append(str(self._port))

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

        cursor.execute('SET FOREIGN_KEY_CHECKS=0')

        # Drop tables.
        cursor.execute('''
            SELECT table_name FROM information_schema.tables
             WHERE table_schema = %s
        ''', (self._database,))

        tables = [row[0] for row in cursor.fetchall()]

        if len(tables) > 0:
            sql = 'DROP TABLE {} '.format(', '.join(tables))
            cursor.execute(sql)

        cursor.execute('SET FOREIGN_KEY_CHECKS=1')

    def connect_db(self):
        ''' Connect to PostgreSQL. '''

        connect_args = {
            'host': self._host,
            'user': self._user,
            'password': self._password,
            'database': self._database,
            'autocommit': True
        }

        if self._port is not None:
            connect_args['port'] = self._port

        return pymysql.connect(**connect_args)

    def restore_db(self, backup_file):
        '''
        Return a ``Popen`` instance that will restore the database from the
        ``backup_file`` handle.
        '''

        env = {'MYSQL_PWD': self._password}

        command = [
            'mysql',
            '-h', self._host,
            '-u', self._user,
        ]

        if self._port is not None:
            command.append('-P')
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
        ''' MySQL does not support schemas. '''

        pass

    def snapshot_db(self, snapshot_file):
        '''
        Return a ``Popen`` instance that writes a snapshot to ``snapshot_file``.
        '''

        env = {'MYSQL_PWD': self._password}

        command = [
            'mysqldump',
            '-h', self._host,
            '-u', self._user,
            '--no-create-db',
            '--no-data',
            '--compact',
        ]

        if self._port is not None:
            command.append('-P')
            command.append(str(self._port))

        command.append(self._database)

        process = subprocess.Popen(
            command,
            env=env,
            stdout=snapshot_file,
            stderr=subprocess.PIPE
        )

        return process

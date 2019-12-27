import os
import subprocess

import pg8000

from agnostic.postgres import PostgresBackend


class TimescaleBackend(PostgresBackend):
    
    def clear_db(self, cursor):
        
        ''' Remove timescale extension. '''

        # Drop extension
        cursor.execute('''
            DROP EXTENSION IF EXISTS timescaledb CASCADE;
        ''')
        
        return super().clear_db(cursor)

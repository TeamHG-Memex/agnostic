import logging
import os
import shutil
import tempfile
import unittest

import agnostic
import agnostic.cli


logging.basicConfig()


class TestUnit(unittest.TestCase):
    ''' Unit tests for Agnostic '''

    def touch_file(self, name):
        with open(name, 'w'):
            pass

    def test_list_migrations(self):
        ''' Migrations should be listed in order. '''
        tempdir = tempfile.mkdtemp(dir='/tmp')
        os.mkdir(tempdir + '/01')
        os.mkdir(tempdir + '/02')
        self.touch_file(tempdir + '/01/2_more_stuff.sql')
        self.touch_file(tempdir + '/02/1_do_stuff.sql')
        self.touch_file(tempdir + '/01/@_sort_bottom.sql')
        self.touch_file(tempdir + '/02/!_sort_top.sql')
        migrations = agnostic.cli._list_migration_files(tempdir)
        self.assertEqual(migrations, [
            '01/2_more_stuff',
            '01/@_sort_bottom',
            '02/!_sort_top',
            '02/1_do_stuff',
        ])
        shutil.rmtree(tempdir)

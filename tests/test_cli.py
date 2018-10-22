import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from click import ClickException
from click.testing import CliRunner

import agnostic
import agnostic.cli


class TestCli(unittest.TestCase):
    def setUp(self):
        ''' Create temporary working directory. '''
        self._temp_dir = tempfile.mkdtemp()
        self._migrations_dir = self._temp_dir + '/migrations'
        self._old_cwd = os.getcwd()
        os.makedirs(self._migrations_dir)
        os.chdir(self._temp_dir)

    def tearDown(self):
        ''' Remove temporary directory. '''
        shutil.rmtree(self._temp_dir)
        os.chdir(self._old_cwd)

    def run_cli(self, command):
        ''' Run CLI and log any errors. '''
        logging.info('Running CLI with args: %r', args)
        result = CliRunner().invoke(agnostic.cli.main, command)

        if result.exception is not None:
            logging.error('== run_cli exception ==')
            logging.error('COMMAND: %s', command)
            logging.error('EXIT CODE: %s', result.exit_code)
            logging.error('OUTPUT:\n%s', result.output)
            raise result.exception

        return result

    def test_invalid_options(self):
        # Invoke CLI with options that pass the argument parser's criteria but
        # fail when instantiating a backend.
        result = CliRunner().invoke(agnostic.cli.main,
            ['-t', 'sqlite', '-u', 'root', '-d', 'test.db', '-m',
                self._migrations_dir, 'bootstrap'])
        self.assertNotEqual(result.exit_code, 0)

    @patch('agnostic.cli.click.confirm')
    def test_drop_requires_confirm(self, mock_confirm):
        result = CliRunner().invoke(agnostic.cli.main,
            ['-t', 'sqlite', '-d', 'test.db', '-m', self._migrations_dir,
                'drop'])
        mock_confirm.assert_called_with('Are you 100% positive that you want '
            'to do this?')
        self.assertNotEqual(result.exit_code, 0)

    @patch('agnostic.cli.click.confirm')
    def test_tester_requires_confirm(self, mock_confirm):
        before = tempfile.mkstemp()[1]
        after = tempfile.mkstemp()[1]
        result = CliRunner().invoke(agnostic.cli.main,
            ['-t', 'sqlite', '-d', 'test.db', '-m', self._migrations_dir,
                'test', before, after])
        os.unlink(before)
        os.unlink(after)
        mock_confirm.assert_called_with('Are you 100% positive that you want '
            'to do this?')
        self.assertNotEqual(result.exit_code, 0)

    def test_list_no_migrations(self):
        result = CliRunner().invoke(agnostic.cli.main,
            ['-t', 'sqlite', '-d', 'test.db', '-m', self._migrations_dir,
                'list'])
        self.assertNotEqual(result.exit_code, 0)

    def test_get_db_cursor_connect_error(self):
        config = MagicMock()
        config.debug = False
        config.backend.connect_db.side_effect = Exception()
        with self.assertRaises(ClickException):
            with agnostic.cli._get_db_cursor(config) as (db, cursor):
                pass

    def test_get_db_cursor_schema_error(self):
        config = MagicMock()
        config.debug = False
        config.backend.get_schema_command.side_effect = Exception()
        with self.assertRaises(ClickException):
            with agnostic.cli._get_db_cursor(config) as (db, cursor):
                pass

    def test_get_db_cursor_closes_automatically(self):
        config = MagicMock()
        config.debug = False
        with agnostic.cli._get_db_cursor(config) as (db, cursor):
            pass
        db.close.assert_called_with()
        # Swallows exception on db.close:
        with agnostic.cli._get_db_cursor(config) as (db, cursor):
            db.close.side_effect = Exception()

    @patch('agnostic.cli._wait_for')
    def test_snapshot_error(self, mock_wait_for):
        mock_wait_for.side_effect = Exception()
        result = CliRunner().invoke(agnostic.cli.main, ['-t', 'sqlite', '-d',
            'test.db', '-m', self._migrations_dir, 'snapshot', 'snapshot.sql'])
        self.assertNotEqual(result.exit_code, 0)

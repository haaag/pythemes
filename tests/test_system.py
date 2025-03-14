from __future__ import annotations

import signal
import subprocess
from unittest.mock import patch

import pytest

from pythemes.__main__ import SysOps


def test_sysops_pid_with_running_process():
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.return_value = b'123 456'
        result = SysOps.pid('test_program')
        mock_check_output.assert_called_once()

        args, kwargs = mock_check_output.call_args
        assert 'pidof' in args[0]
        assert 'test_program' in args[0]
        assert result == [123, 456]


def test_sysops_pid_with_no_processes():
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = subprocess.CalledProcessError(
            1, cmd='pidof nonexistent', output=b''
        )
        with pytest.raises(subprocess.CalledProcessError):
            SysOps.pid('nonexistent')


def test_sysops_pid_with_single_process():
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.return_value = b'789'
        result = SysOps.pid('single_program')
        assert result == [789]


def test_sysops_send_signal_success():
    with patch('os.kill') as mock_kill:
        test_pids = [1234, 5678]
        test_signal = signal.SIGTERM
        expected_n_call = 2
        SysOps.send_signal(test_pids, test_signal)

        assert mock_kill.call_count == expected_n_call
        mock_kill.assert_any_call(1234, test_signal)
        mock_kill.assert_any_call(5678, test_signal)


def test_sysops_send_signal_handles_oserror():
    with patch('os.kill') as mock_kill:
        mock_kill.side_effect = OSError('Process does not exist')
        test_pids = [9999]
        test_signal = signal.SIGTERM
        with pytest.raises(OSError):
            SysOps.send_signal(test_pids, test_signal)


def test_sysops_send_signal_empty_pid_list():
    with patch('os.kill') as mock_kill:
        SysOps.send_signal([], signal.SIGTERM)
        mock_kill.assert_not_called()


def test_sysops_send_signal_different_signals():
    with patch('os.kill') as mock_kill:
        the_pid = 1000
        test_pid = [the_pid]
        # SIGTERM signal
        SysOps.send_signal(test_pid, signal.SIGTERM)
        mock_kill.assert_called_with(the_pid, signal.SIGTERM)
        # SIGKILL signal
        mock_kill.reset_mock()
        SysOps.send_signal(test_pid, signal.SIGKILL)
        mock_kill.assert_called_with(the_pid, signal.SIGKILL)


def test_sysops_run_successful_command():
    with patch('subprocess.run') as mock_run:
        mock_process = mock_run.return_value
        mock_process.returncode = 0

        result = SysOps.run('echo test')
        assert result == 0

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert 'echo' in args[0][0]
        assert 'test' in args[0][1]
        assert kwargs['check'] is False
        assert kwargs['shell'] is False


def test_sysops_run_failed_command():
    with patch('subprocess.run') as mock_run:
        mock_process = mock_run.return_value
        mock_process.returncode = 1
        result = SysOps.run('invalid command')
        assert result == 1


def test_sysops_run_file_not_found():
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = FileNotFoundError('No such file or directory')
        result = SysOps.run('nonexistent')
        assert result == 1

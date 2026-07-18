import unittest
from unittest.mock import patch, MagicMock
from main import SafeCommandRunner

class TestSafeCommandRunner(unittest.TestCase):
    def setUp(self):
        self.runner = SafeCommandRunner()

    @patch('rich.console.Console.input', return_value='y')
    def test_request_human_approval_approved(self, mock_input):
        result = self.runner.request_human_approval('df -h', 'check disk space')
        self.assertIn("Approved", result)
        self.assertIn('df -h', self.runner.approved_commands)

    @patch('rich.console.Console.input', return_value='n')
    def test_request_human_approval_rejected(self, mock_input):
        result = self.runner.request_human_approval('df -h', 'check disk space')
        self.assertIn("Rejected", result)
        self.assertNotIn('df -h', self.runner.approved_commands)

    def test_execute_command_without_approval(self):
        result = self.runner.execute_command('df -h', 'check disk space')
        self.assertIn("Error", result)
        self.assertIn("obtain approval", result)

    @patch('rich.console.Console.input', return_value='y')
    @patch('subprocess.run')
    def test_execute_command_with_approval_success(self, mock_subprocess, mock_input):
        # Mock subprocess response
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        50G   20G   30G  40% /"
        mock_subprocess.return_value = mock_res
        
        approval_res = self.runner.request_human_approval('df -h', 'check disk space')
        self.assertIn("Approved", approval_res)
        
        exec_res = self.runner.execute_command('df -h', 'check disk space')
        self.assertIn("Success", exec_res)
        self.assertIn("/dev/sda1", exec_res)

    @patch('rich.console.Console.input', return_value='y')
    @patch('subprocess.run')
    def test_execute_arbitrary_approved_command(self, mock_subprocess, mock_input):
        # Mock subprocess response
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "hello\n"
        mock_subprocess.return_value = mock_res
        
        approval_res = self.runner.request_human_approval("echo 'hello'", 'test custom command')
        self.assertIn("Approved", approval_res)
        
        exec_res = self.runner.execute_command("echo 'hello'", 'test custom command')
        self.assertIn("Success", exec_res)
        self.assertIn("hello", exec_res)

if __name__ == '__main__':
    unittest.main()

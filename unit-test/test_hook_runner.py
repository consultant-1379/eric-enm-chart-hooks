from unittest import TestCase

from hook_runner import exec_hook


class TestHookRunner(TestCase):
    def test_exec_hook_no_args(self):
        self.assertRaises(SystemExit, exec_hook, [])

    def test_exec_hook_not_found(self):
        self.assertRaises(SystemExit, exec_hook, ['some_file'])
        self.assertRaises(SystemExit, exec_hook, ['/a/b/c/some_file'])

    def test_exec_hook(self):
        self.assertRaises(SystemExit, exec_hook, ['/bin/false'])
        exec_hook(['/bin/true'])

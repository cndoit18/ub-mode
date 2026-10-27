import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UB = ROOT / "bin" / "ub"
NETWORK = os.environ.get("UB_NETWORK_TESTS") == "1"


def run_ub(home, *args, cwd=ROOT, timeout=60):
    env = os.environ.copy()
    env["UB_MODE_HOME"] = str(home)
    return subprocess.run(
        [str(UB), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


class UnifiedCommandTest(unittest.TestCase):
    def test_help_lists_the_tools_without_installing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            result = run_ub(home, "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            for tool in ("crapper", "dryer", "mutator", "uml"):
                self.assertIn(tool, result.stdout)
            self.assertFalse((home / "venv").exists())

    def test_unknown_tool_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_ub(Path(directory), "unknown")
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown tool: unknown", result.stderr)

    def test_tool_receives_arguments_and_project_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            executable = home / "venv" / "bin" / "crapper"
            executable.parent.mkdir(parents=True)
            executable.write_text(
                "#!/bin/sh\nprintf 'tool=%s args=%s cwd=%s\\n' "
                "\"$(basename \"$0\")\" \"$*\" \"$PWD\"\n"
            )
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
            result = run_ub(home, "crapper", "--threshold", "10", "src")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout,
                f"tool=crapper args=--threshold 10 src cwd={ROOT}\n",
            )

    @unittest.skipUnless(NETWORK, "set UB_NETWORK_TESTS=1 to fetch real tools")
    def test_first_use_installs_all_python_tools_and_install_is_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            project = Path(directory) / "project"
            project.mkdir()
            result = run_ub(home, "crapper", "--help", cwd=project, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Usage: crapper", result.stdout)
            for tool in ("crapper", "dryer", "mutator"):
                result = run_ub(home, tool, "--help", cwd=project)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"sage: {tool}", result.stdout)
            result = run_ub(home, "install", cwd=project, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(project.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

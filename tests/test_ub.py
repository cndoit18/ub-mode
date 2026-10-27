from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).absolute().parents[1]
UB = ROOT / "bin" / "ub"
SPEC = importlib.util.spec_from_file_location("ub", ROOT / "bin" / "ub.py")
ub = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ub)
NETWORK = os.environ.get("UB_NETWORK_TESTS") == "1"


def run_ub(home, *args, cwd=ROOT, timeout=60):
    env = os.environ.copy()
    env["UB_MODE_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(UB), *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )


class UnifiedCommandTest(unittest.TestCase):
    def test_data_home_uses_override_then_xdg_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "ub"
            with patch.dict(os.environ, {"UB_MODE_HOME": str(home)}):
                self.assertEqual(ub.data_home(), home)
            with patch.dict(os.environ, {"XDG_DATA_HOME": directory}, clear=True):
                self.assertEqual(ub.data_home(), Path(directory) / "ub-mode")

    def test_venv_python_uses_the_platform_script_directory(self):
        home = Path("home")
        self.assertEqual(ub.venv_python(home), home / "venv" / "bin" / "python")

    def test_in_process_commands_cover_help_and_tool_dispatch(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(ub.main([]), 0)
            self.assertEqual(ub.main(["--help"]), 0)
            self.assertEqual(ub.main(["unknown"]), 2)
        self.assertIn("crapper", stdout.getvalue())
        self.assertIn("unknown tool: unknown", stderr.getvalue())

        completed = subprocess.CompletedProcess([], 7)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            with patch.dict(os.environ, {"UB_MODE_HOME": str(home)}), patch.object(
                ub, "ensure_python_tool", return_value=Path("crapper")
            ) as ensure, patch.object(ub.subprocess, "run", return_value=completed) as run:
                self.assertEqual(ub.main(["crapper", "--changed"]), 7)
                ensure.assert_called_once_with(home, "crapper")
                run.assert_called_once_with(["crapper", "--changed"])

            with patch.dict(os.environ, {"UB_MODE_HOME": str(home)}), patch.object(
                ub, "install_python_tools"
            ) as install:
                self.assertEqual(ub.main(["install"]), 0)
                install.assert_called_once_with(home)

    def test_install_creates_environment_and_installs_all_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "missing" / "home"
            with patch.object(ub.subprocess, "run") as run:
                ub.install_python_tools(home)
                ub.install_python_tools(home)
            self.assertEqual(run.call_count, 4)
            first_create, first_install, second_create, second_install = run.call_args_list
            self.assertEqual(first_create.args[0][1:4], ["-m", "venv", str(home / "venv")])
            self.assertEqual(second_create, first_create)
            for create in (first_create, second_create):
                self.assertTrue(create.kwargs["check"])
            for install in (first_install, second_install):
                self.assertEqual(install.args[0][1:4], ["-m", "pip", "install"])
                self.assertTrue(install.kwargs["check"])
            self.assertTrue(first_install.args[0][-1].endswith("requirements.txt"))
            self.assertTrue(second_install.args[0][-1].endswith("requirements.txt"))

    def test_venv_creation_failure_stops_before_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            script = Path(directory) / "check.py"
            script.write_text(
                "import sys\n"
                "from unittest.mock import patch\n"
                f"sys.path.insert(0, {str(ROOT)!r})\n"
                "from tests.test_ub import ub\n"
                f"failure = __import__('subprocess').CalledProcessError(1, ['venv'])\n"
                "with patch.object(ub.subprocess, 'run', side_effect=failure) as run:\n"
                f"    ub.install_python_tools(__import__('pathlib').Path({str(home)!r}))\n"
            )
            result = subprocess.run(
                [sys.executable, str(script)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CalledProcessError", result.stderr)

    def test_existing_python_tool_does_not_trigger_reinstall(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            executable = ub.venv_python(home).parent / "dryer"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.object(ub, "install_python_tools") as install:
                self.assertEqual(ub.ensure_python_tool(home, "dryer"), executable)
                install.assert_not_called()

    def test_uml_installs_once_then_forwards_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                completed = subprocess.CompletedProcess([], 0)
                def download(*args, **kwargs):
                    if "-o" in args[0]:
                        Path(args[0][-1]).touch()
                    return completed
                with patch.object(ub.subprocess, "run", side_effect=download) as run:
                    self.assertEqual(ub.run_uml(["--help"]), 0)
                    self.assertTrue(Path("get-uml-viewer").stat().st_mode & stat.S_IXUSR)
                    self.assertEqual(run.call_count, 3)
                    for install in run.call_args_list[:2]:
                        self.assertTrue(install.kwargs["check"])
                    Path("uml").touch()
                    self.assertEqual(ub.run_uml(["--restart"]), 0)
                    self.assertEqual(run.call_count, 4)
                self.assertEqual(run.call_args.args[0], ["./uml", "--restart"])
            finally:
                os.chdir(previous)

    def test_help_lists_the_tools_without_installing_them(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            result = run_ub(home, "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            for tool in ("crapper", "dryer", "mutator", "uml"):
                self.assertIn(tool, result.stdout)
            self.assertFalse((home / "venv").exists())
            direct = subprocess.run(
                [sys.executable, str(ROOT / "bin" / "ub.py"), "--help"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(direct.returncode, 0, direct.stderr)
            self.assertEqual(direct.stdout, result.stdout)

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

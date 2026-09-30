"""Execute the small test-command allowlist only in disposable Docker containers."""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .config import settings
from .security import SECRET_NAMES, redact_secrets


class CommandRejected(ValueError):
    pass


def validate_command(command: str | list[str]) -> list[str]:
    """No shell language, executable selection, arbitrary Python, or unsafe paths."""
    if isinstance(command, str):
        if any(char in command for char in ";&|`$<>\n\r\x00"):
            raise CommandRejected("Shell syntax is prohibited; provide a permitted test command.")
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            raise CommandRejected("Invalid command quoting.") from exc
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        argv = list(command)
    else:
        raise CommandRejected("Command must be a string or an array of strings.")
    if not argv or len(argv) > 24 or any(len(item) > 300 for item in argv):
        raise CommandRejected("Command is empty or exceeds argument limits.")
    if argv[:3] == ["python", "-m", "pytest"]:
        tail = argv[3:]
    elif argv[0] == "pytest":
        tail = argv[1:]
    elif argv[:2] == ["npm", "test"]:
        if argv[2:] not in ([], ["--", "--runInBand"], ["--", "--watch=false"]):
            raise CommandRejected("npm supports only test and the documented test flags.")
        return argv
    else:
        raise CommandRejected("Only pytest, python -m pytest, and npm test are permitted.")
    flags = {"-q", "-v", "-vv", "-x", "--disable-warnings", "--maxfail=1", "--tb=short", "--tb=line"}
    for argument in tail:
        if argument in flags:
            continue
        path = argument.split("::", 1)[0]
        if (argument.startswith("-") or not re.fullmatch(r"[A-Za-z0-9_./:-]+", argument)
                or ".." in path.split("/") or path.startswith("/") or "\\" in argument
                or ":" in path or not path):
            raise CommandRejected(f"Unsafe or unsupported pytest argument: {argument!r}")
    return argv


def copy_repository(source: Path, destination: Path) -> None:
    """Copy regular files only; never follow repository symlinks or copy credentials."""
    ignored = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build",
               ".ssh", ".aws", ".kube"}
    count, total = 0, 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = [name for name in dirs if name not in ignored and not (Path(directory) / name).is_symlink()]
        for name in files:
            original = Path(directory) / name
            if original.is_symlink() or not original.is_file() or name in SECRET_NAMES or name.startswith(".env."):
                continue
            if name.lower().endswith((".pem", ".key", ".p12", ".pfx")):
                continue
            size = original.stat().st_size
            count += 1
            total += size
            if count > 10000 or total > 100 * 1024 * 1024 or size > 10 * 1024 * 1024:
                raise ValueError("Sandbox snapshot exceeds bounded repository size.")
            target = destination / original.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)


class DockerSandbox:
    def available(self) -> bool:
        if not settings.sandbox_enabled or not shutil.which("docker"):
            return False
        try:
            result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                                    capture_output=True, timeout=5, check=False)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def run(self, root_path: str | Path, command: str | list[str]) -> dict:
        started = time.perf_counter()
        try:
            argv = validate_command(command)
        except CommandRejected as exc:
            return {"status": "rejected", "success": False, "executed": False, "command": command,
                    "exit_code": None, "output": str(exc), "duration_ms": 0}
        if not self.available():
            return {"status": "unavailable", "success": False, "executed": False, "command": argv,
                    "exit_code": None, "output": "Docker sandbox is unavailable. No tests were executed.",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2)}
        root = Path(root_path).resolve()
        if not root.is_dir():
            raise ValueError("Repository working copy is unavailable.")
        name = "repopilot-" + uuid.uuid4().hex
        timeout = max(1, min(int(settings.sandbox_timeout), 300))
        maximum_output = max(1000, min(getattr(settings, "sandbox_max_output", 20000), 100000))
        container_image = (getattr(settings, "sandbox_node_image", "node:22-alpine")
                           if argv[0] == "npm" else getattr(settings, "sandbox_image", "repopilot-sandbox:local"))
        process = None
        try:
            with tempfile.TemporaryDirectory(prefix="repopilot-sandbox-") as temporary:
                snapshot = Path(temporary) / "source"
                snapshot.mkdir()
                copy_repository(root, snapshot)
                if "," in str(snapshot):
                    raise ValueError("Sandbox path contains an unsupported mount separator.")
                docker_argv = [
                    "docker", "run", "--rm", "--pull=never", "--name", name,
                    "--network", "none", "--read-only", "--cap-drop", "ALL",
                    "--security-opt", "no-new-privileges", "--user", "65534:65534",
                    "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
                    "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
                    "--tmpfs", "/workspace:rw,nosuid,size=128m,uid=65534,gid=65534,mode=0700",
                    "--mount", f"type=bind,source={snapshot},target=/source,readonly",
                    "--workdir", "/workspace", "--env", "PYTHONDONTWRITEBYTECODE=1",
                    "--env", "CI=true", container_image, "sh", "-c",
                    'cp -R /source/. /workspace/ && exec "$@"', "sandbox", *argv,
                ]
                output_path = Path(temporary) / "output.log"
                timed_out, output_limited = False, False
                with output_path.open("wb") as output:
                    process = subprocess.Popen(docker_argv, stdout=output, stderr=subprocess.STDOUT, shell=False)
                    deadline = time.monotonic() + timeout
                    while process.poll() is None:
                        if time.monotonic() >= deadline:
                            timed_out = True
                            process.kill()
                            break
                        if output_path.stat().st_size > 10 * 1024 * 1024:
                            output_limited = True
                            process.kill()
                            break
                        time.sleep(0.1)
                    process.wait(timeout=5)
                with output_path.open("rb") as output:
                    captured = redact_secrets(output.read(maximum_output).decode("utf-8", errors="replace"))
                truncated = output_path.stat().st_size > maximum_output
                if truncated:
                    captured += "\n[Output truncated]"
                status = "timeout" if timed_out else "output_limit" if output_limited else "passed" if process.returncode == 0 else "failed"
                # Docker's own launch failure means the repository command did not execute.
                executed = process.returncode not in {125, 126, 127}
                if not executed and status == "failed":
                    status = "unavailable"
                return {"status": status, "success": status == "passed", "executed": executed,
                        "command": argv, "exit_code": process.returncode, "output": captured,
                        "truncated": truncated, "duration_ms": round((time.perf_counter() - started) * 1000, 2)}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return {"status": "unavailable", "success": False, "executed": False, "command": argv,
                    "exit_code": None, "output": f"Sandbox could not execute: {exc}",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2)}
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                try:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10, check=False)
                except (OSError, subprocess.SubprocessError):
                    pass

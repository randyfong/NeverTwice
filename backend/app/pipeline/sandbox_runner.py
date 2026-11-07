import asyncio
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from backend.app.config import settings


async def run_in_sandbox(patch_code: str, test_suite: str) -> dict[str, Any]:
    """
    Executes generated code and tests inside an isolated temporary directory
    using a pytest subprocess with an enforced execution budget.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 1. Write the candidate solution file
        solution_file = tmp_path / "solution.py"
        solution_file.write_text(patch_code, encoding="utf-8")

        # 2. Write the test suite importing from solution
        test_content = (
            "import pytest\n"
            "from solution import *\n\n"
            f"{test_suite}\n"
        )
        test_file = tmp_path / "test_suite.py"
        test_file.write_text(test_content, encoding="utf-8")

        # Use current virtualenv's python binary
        python_bin = sys.executable

        # 3. Execute pytest subprocess
        try:
            proc = await asyncio.create_subprocess_exec(
                python_bin, "-m", "pytest", str(test_file), "-q", "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=settings.SANDBOX_TIMEOUT_SECONDS,
            )
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Parse counts from pytest summary line (e.g. "1 passed", "2 failed, 1 passed")
            passed_match = re.search(r"(\d+)\s+passed", stdout_str)
            failed_match = re.search(r"(\d+)\s+failed", stdout_str)

            passed_count = int(passed_match.group(1)) if passed_match else 0
            failed_count = int(failed_match.group(1)) if failed_match else 0
            total = passed_count + failed_count

            all_passed = (proc.returncode == 0) and (failed_count == 0)

            return {
                "passed": all_passed,
                "tests_run": total if total > 0 else (1 if proc.returncode == 0 else 0),
                "tests_passed": passed_count,
                "tests_failed": failed_count,
                "failed": failed_count,  # backward compatibility alias
                "stdout": stdout_str if stdout_str else stderr_str,
                "stderr": stderr_str,
            }
        except asyncio.TimeoutError:
            return {
                "passed": False,
                "tests_run": 1,
                "tests_passed": 0,
                "tests_failed": 1,
                "failed": 1,
                "stdout": f"Sandbox execution aborted: {settings.SANDBOX_TIMEOUT_SECONDS}s timeout exceeded (possible infinite loop or deadlocked lock).",
                "stderr": "ExecutionTimeout",
            }

"""bb-browser backend -- wraps the bb-browser CLI.

Requires: npm install -g bb-browser + Chrome extension.
All commands delegate to ``bb-browser <subcommand> --json`` via
asyncio.create_subprocess_exec with a 30-second timeout.
"""
from __future__ import annotations

import asyncio
import base64
import json
import shutil
from typing import Any

from maestro_fetch.core.errors import FetchError

_TIMEOUT = 30  # seconds


class BbBrowserBackend:
    """Wraps the ``bb-browser`` CLI as a BrowserBackend."""

    name: str = "bb-browser"

    # -- helpers --------------------------------------------------------

    @staticmethod
    async def _run(*cmd: str, timeout: int = _TIMEOUT) -> dict:
        """Run a bb-browser subcommand and return parsed JSON output.

        Raises FetchError on timeout, non-zero exit, or invalid JSON.
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise FetchError(
                f"bb-browser timed out after {timeout}s: {' '.join(cmd)}"
            )

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            raise FetchError(
                f"bb-browser exited {proc.returncode}: {err_msg}"
            )

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise FetchError(
                f"bb-browser returned invalid JSON: {exc}"
            ) from exc

    # -- protocol methods -----------------------------------------------

    async def is_available(self) -> bool:
        """Return True if ``bb-browser`` is on PATH."""
        return shutil.which("bb-browser") is not None

    async def fetch_content(self, url: str) -> str:
        """Fetch *url* via ``bb-browser fetch <url> --json`` and return markdown."""
        result = await self._run("bb-browser", "fetch", url, "--json")
        return result.get("content", "")

    async def fetch_screenshot(self, url: str) -> bytes:
        """Screenshot *url* via ``bb-browser screenshot --json``, return PNG bytes."""
        result = await self._run("bb-browser", "screenshot", url, "--json")
        b64 = result.get("screenshot", "")
        return base64.b64decode(b64)

    async def eval_js(self, js: str) -> Any:
        """Execute *js* via ``bb-browser eval "<js>" --json``."""
        result = await self._run("bb-browser", "eval", js, "--json")
        return result.get("result")

    async def site_adapter(self, adapter_name: str, *args: str) -> dict:
        """Run ``bb-browser site <name> <args> --json``."""
        return await self._run(
            "bb-browser", "site", adapter_name, *args, "--json"
        )

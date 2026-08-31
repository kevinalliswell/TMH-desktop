"""Safe, non-blocking-friendly GitHub release checks for the desktop app."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.utils.logger import get_logger


REPOSITORY = "kevinalliswell/TMH-desktop"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
MAX_RESPONSE_BYTES = 64 * 1024
_VERSION_PATTERN = re.compile(r"^[vV]?(\d+(?:\.\d+)*)$")


@dataclass(frozen=True)
class UpdateCheckResult:
    current_version: str
    latest_version: str | None = None
    update_available: bool = False
    release_url: str | None = None
    error: str | None = None


def parse_version(version: str) -> tuple[int, ...]:
    """Parse the numeric release format used by ``software.info`` and tags."""
    match = _VERSION_PATTERN.fullmatch(str(version).strip())
    if not match:
        raise ValueError(f"invalid release version: {version!r}")
    return tuple(int(component) for component in match.group(1).split("."))


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_parts = parse_version(candidate)
    current_parts = parse_version(current)
    width = max(len(candidate_parts), len(current_parts))
    return candidate_parts + (0,) * (width - len(candidate_parts)) > (
        current_parts + (0,) * (width - len(current_parts))
    )


class UpdateService:
    """Query the latest GitHub release without ever failing the application."""

    def __init__(self, *, opener=urlopen, timeout: float = 5.0):
        self._opener = opener
        self.timeout = timeout
        self.logger = get_logger(__name__)

    def check(self, current_version: str) -> UpdateCheckResult:
        try:
            request = Request(
                LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "TMH-LPF-900-update-check",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            with self._opener(request, timeout=self.timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("release response is too large")

            payload = json.loads(body.decode("utf-8"))
            tag = str(payload["tag_name"]).strip()
            latest_version = tag[1:] if tag[:1].lower() == "v" else tag
            update_available = is_newer_version(latest_version, current_version)
            return UpdateCheckResult(
                current_version=current_version,
                latest_version=latest_version,
                update_available=update_available,
                release_url=self._safe_release_url(payload.get("html_url")),
            )
        except Exception as exc:
            self.logger.warning("软件更新检查失败: %s", exc)
            return UpdateCheckResult(
                current_version=current_version,
                error=str(exc),
            )

    @staticmethod
    def _safe_release_url(value) -> str:
        parsed = urlparse(str(value or ""))
        expected_prefix = f"/{REPOSITORY}/releases"
        if (
            parsed.scheme == "https"
            and parsed.netloc.lower() == "github.com"
            and (
                parsed.path == expected_prefix
                or parsed.path.startswith(f"{expected_prefix}/")
            )
        ):
            return str(value)
        return RELEASES_PAGE

"""Whitelist enforcement utilities for agent tasks."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Default domains that the agent is allowed to interact with when no runtime
# configuration is provided. The list favours well-known documentation sources
# but can be overridden by the ``AURA_WHITELIST`` environment variable.
DEFAULT_ALLOWED_DOMAINS: Tuple[str, ...] = (
    "docs.python.org",
    "developer.mozilla.org",
    "pypi.org",
)

# Matches URLs with an explicit scheme or that start with ``www.``. The captured
# value is later normalised before the domain is extracted.
_URL_PATTERN = re.compile(r"(?P<url>(?:https?://|www\.)[^\s]+)", re.IGNORECASE)


class WhitelistValidationError(PermissionError):
    """Raised when a user request violates the whitelist rules."""


@dataclass(frozen=True)
class WhitelistConfig:
    """Configuration container used by the validation helpers."""

    allowed_domains: Tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "WhitelistConfig":
        """Build a configuration object from environment variables."""

        raw = os.getenv("AURA_WHITELIST", "")
        if raw:
            domains = tuple(
                domain.strip().lower()
                for domain in raw.split(",")
                if domain.strip()
            )
            if domains:
                return cls(domains)
        return cls(DEFAULT_ALLOWED_DOMAINS)


def get_allowed_domains(config: WhitelistConfig | None = None) -> Tuple[str, ...]:
    """Return the tuple of domains that are permitted."""

    config = config or WhitelistConfig.from_environment()
    return config.allowed_domains


def extract_candidate_urls(text: str) -> List[str]:
    """Extract potential URLs from the provided text."""

    if not text:
        return []
    return [match.group("url") for match in _URL_PATTERN.finditer(text)]


def _normalise_url(candidate: str) -> str:
    if candidate.lower().startswith(("http://", "https://")):
        return candidate
    return f"http://{candidate}"


def extract_domains(text: str) -> List[str]:
    """Return a list of domains referenced in the text."""

    domains: List[str] = []
    for url in extract_candidate_urls(text):
        parsed = urlparse(_normalise_url(url))
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            domains.append(domain)
    return domains


def _matches_pattern(domain: str, pattern: str) -> bool:
    domain = domain.lower()
    pattern = pattern.lower()
    if not pattern:
        return False
    if pattern.startswith("*."):
        suffix = pattern[2:]
        return domain == suffix or domain.endswith(f".{suffix}")
    return domain == pattern


def is_domain_allowed(domain: str, allowed_domains: Sequence[str]) -> bool:
    """Check whether ``domain`` matches at least one allowed pattern."""

    for pattern in allowed_domains:
        if _matches_pattern(domain, pattern):
            return True
    return False


def validate_task_description(
    task_description: str,
    *,
    allowed_domains: Iterable[str] | None = None,
) -> None:
    """Validate that the user task obeys the whitelist constraints."""

    domains = extract_domains(task_description)
    if not domains:
        logger.debug("No domains discovered in task; whitelist passes by default.")
        return

    allowed = tuple(domain.lower() for domain in (allowed_domains or get_allowed_domains()))
    invalid = sorted({domain for domain in domains if not is_domain_allowed(domain, allowed)})
    if invalid:
        allowed_display = ", ".join(allowed) or "(empty)"
        message = (
            "The requested task references domains outside the whitelist: "
            f"{', '.join(invalid)}. Allowed domains: {allowed_display}."
        )
        logger.error(message)
        raise WhitelistValidationError(message)

    logger.info("Whitelist validation succeeded for domains: %s", ", ".join(sorted(set(domains))))


def whitelist_pre_run_hook(task_description: str) -> None:
    """Hook compatible function that enforces whitelist rules."""

    validate_task_description(task_description)

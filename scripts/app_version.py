#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_INFO_PATH = PROJECT_ROOT / "configs" / "software.info"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def load_software_info() -> dict:
    return json.loads(SOFTWARE_INFO_PATH.read_text(encoding="utf-8"))


def get_version() -> str:
    return str(load_software_info()["version"]).strip()


def get_tag() -> str:
    return f"v{get_version()}"


def validate(version: str) -> None:
    if not VERSION_PATTERN.match(version):
        raise ValueError(
            f"Invalid app version '{version}'. Expected semantic version digits like 1.2.3."
        )


def write_github_output(version: str, tag: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return

    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"version={version}\n")
        handle.write(f"tag={tag}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read and validate the app version from configs/software.info.")
    parser.add_argument(
        "--format",
        choices=("version", "tag"),
        default="version",
        help="Choose whether to print the plain version or the Git tag form.",
    )
    parser.add_argument(
        "--check-tag",
        help="Fail unless the provided tag exactly matches the configured app version.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate that the configured version is semantic-version compatible.",
    )
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="Write version and tag to the GitHub Actions output file when available.",
    )
    args = parser.parse_args()

    version = get_version()
    tag = f"v{version}"

    try:
        if args.validate:
            validate(version)
        if args.check_tag and args.check_tag != tag:
            raise ValueError(
                f"Tag mismatch: expected '{tag}' from configs/software.info but got '{args.check_tag}'."
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.github_output:
        write_github_output(version, tag)

    print(tag if args.format == "tag" else version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


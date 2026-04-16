#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_INFO_PATH = PROJECT_ROOT / "configs" / "software.info"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
RELEASE_HEADING_PATTERN = re.compile(r"^## \[(?P<version>[^\]]+)\] - (?P<release_date>\d{4}-\d{2}-\d{2})$", re.MULTILINE)


@dataclass(frozen=True)
class ReleaseSection:
    version: str
    release_date: str
    body: str


def validate_version(value: str) -> str:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError(
            f"Invalid version '{value}'. Expected digits in the form MAJOR.MINOR.PATCH."
        )
    return value


def validate_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc
    return value


def load_software_info(path: Path = SOFTWARE_INFO_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_software_info(info: dict, path: Path = SOFTWARE_INFO_PATH) -> None:
    path.write_text(json.dumps(info, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def load_changelog(path: Path = CHANGELOG_PATH) -> str:
    return path.read_text(encoding="utf-8")


def save_changelog(text: str, path: Path = CHANGELOG_PATH) -> None:
    path.write_text(text, encoding="utf-8")


def get_first_release_section(changelog_text: str) -> ReleaseSection | None:
    headings = list(RELEASE_HEADING_PATTERN.finditer(changelog_text))
    if not headings:
        return None

    first = headings[0]
    body_start = first.end()
    body_end = headings[1].start() if len(headings) > 1 else len(changelog_text)
    body = changelog_text[body_start:body_end].strip()
    return ReleaseSection(
        version=first.group("version"),
        release_date=first.group("release_date"),
        body=body,
    )


def split_unreleased_section(changelog_text: str) -> tuple[str, str, str]:
    marker = "## [Unreleased]"
    start = changelog_text.find(marker)
    if start == -1:
        raise ValueError("CHANGELOG.md is missing the '## [Unreleased]' section.")

    after_start = start + len(marker)
    next_heading = re.search(r"^## \[", changelog_text[after_start:], flags=re.MULTILINE)
    end = after_start + next_heading.start() if next_heading else len(changelog_text)

    prefix = changelog_text[:start]
    body = changelog_text[after_start:end]
    suffix = changelog_text[end:]
    return prefix, body, suffix


def normalize_release_body(body: str) -> str:
    stripped = body.strip()
    if not stripped:
        return "### Changed\n\n- No notable changes documented."
    return stripped


def prepare_release(
    version: str,
    release_date: str,
    *,
    software_info_path: Path = SOFTWARE_INFO_PATH,
    changelog_path: Path = CHANGELOG_PATH,
    dry_run: bool = False,
) -> tuple[dict, str]:
    validate_version(version)
    validate_date(release_date)

    info = load_software_info(software_info_path)
    changelog_text = load_changelog(changelog_path)

    if re.search(rf"^## \[{re.escape(version)}\] - ", changelog_text, flags=re.MULTILINE):
        raise ValueError(f"CHANGELOG.md already contains a release entry for {version}.")

    prefix, unreleased_body, suffix = split_unreleased_section(changelog_text)
    release_body = normalize_release_body(unreleased_body)

    updated_info = deepcopy(info)
    updated_info["version"] = version
    updated_info["release_date"] = release_date
    updated_info["build_date"] = release_date

    rebuilt = prefix.rstrip()
    rebuilt += f"\n\n## [Unreleased]\n\n## [{version}] - {release_date}\n\n{release_body}\n"
    if suffix.strip():
        rebuilt += "\n" + suffix.lstrip("\n")
    else:
        rebuilt += "\n"

    if not dry_run:
        save_software_info(updated_info, software_info_path)
        save_changelog(rebuilt, changelog_path)

    return updated_info, rebuilt


def verify_release_metadata(
    *,
    software_info_path: Path = SOFTWARE_INFO_PATH,
    changelog_path: Path = CHANGELOG_PATH,
    check_tag: str | None = None,
) -> dict:
    info = load_software_info(software_info_path)
    version = validate_version(str(info.get("version", "")).strip())
    release_date = validate_date(str(info.get("release_date", "")).strip())
    validate_date(str(info.get("build_date", "")).strip())

    if check_tag and check_tag != f"v{version}":
        raise ValueError(
            f"Tag mismatch: expected 'v{version}' from configs/software.info but got '{check_tag}'."
        )

    changelog_text = load_changelog(changelog_path)
    first_release = get_first_release_section(changelog_text)
    if first_release is None:
        raise ValueError("CHANGELOG.md does not contain any released version sections.")

    if first_release.version != version:
        raise ValueError(
            "Version mismatch: configs/software.info points to "
            f"{version}, but the latest CHANGELOG release is {first_release.version}."
        )

    if first_release.release_date != release_date:
        raise ValueError(
            "Release date mismatch: configs/software.info has "
            f"{release_date}, but CHANGELOG.md has {first_release.release_date}."
        )

    return {
        "version": version,
        "tag": f"v{version}",
        "release_date": release_date,
    }


def cmd_show(_: argparse.Namespace) -> int:
    try:
        result = verify_release_metadata()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        result = verify_release_metadata(check_tag=args.check_tag)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    version = validate_version(args.version)
    release_date = validate_date(args.date or date.today().isoformat())

    try:
        info, changelog = prepare_release(
            version,
            release_date,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        print()
        print(changelog)
    else:
        print(
            f"Prepared release {info['version']} for {info['release_date']} "
            "and synchronized configs/software.info with CHANGELOG.md."
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage TMH release metadata and keep software.info plus CHANGELOG in sync."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="Show the current validated release metadata.")
    show_parser.set_defaults(func=cmd_show)

    verify_parser = subparsers.add_parser("verify", help="Verify that version metadata is internally consistent.")
    verify_parser.add_argument("--check-tag", help="Fail unless the provided Git tag matches configs/software.info.")
    verify_parser.set_defaults(func=cmd_verify)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Cut a release from CHANGELOG Unreleased and update configs/software.info.",
    )
    prepare_parser.add_argument("--version", required=True, help="New release version, for example 1.1.251122.")
    prepare_parser.add_argument(
        "--date",
        help="Release date in YYYY-MM-DD. Defaults to today.",
    )
    prepare_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    prepare_parser.set_defaults(func=cmd_prepare)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

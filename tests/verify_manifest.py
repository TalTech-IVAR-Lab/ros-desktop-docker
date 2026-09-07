#!/usr/bin/env python3
"""Verify published Docker manifests contain the required platforms."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass


EXPECTED_PLATFORMS = {("linux", "amd64"), ("linux", "arm64")}


@dataclass(frozen=True)
class ManifestResult:
    reference: str
    digest: str
    platforms: frozenset[tuple[str, str]]


def inspect_manifest(reference: str) -> ManifestResult:
    command = [
        "docker",
        "buildx",
        "imagetools",
        "inspect",
        reference,
        "--format",
        "{{json .Manifest}}",
    ]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"could not inspect {reference}: {completed.stderr.strip()}"
        )

    manifest = json.loads(completed.stdout)
    platforms = frozenset(
        (entry.get("platform", {}).get("os"), entry.get("platform", {}).get("architecture"))
        for entry in manifest.get("manifests", [])
        if entry.get("platform", {}).get("os") != "unknown"
    )
    return ManifestResult(reference, manifest.get("digest", ""), platforms)


def verify_manifest(reference: str) -> ManifestResult:
    result = inspect_manifest(reference)
    if result.platforms != EXPECTED_PLATFORMS:
        expected = sorted(EXPECTED_PLATFORMS)
        actual = sorted(result.platforms)
        raise RuntimeError(
            f"{reference} platforms differ: expected {expected}, found {actual}"
        )
    if not result.digest.startswith("sha256:"):
        raise RuntimeError(f"{reference} did not report a sha256 manifest digest")
    print(
        f"MANIFEST_VERIFY=PASS reference={reference} digest={result.digest} "
        f"platforms={','.join(f'{os_name}/{arch}' for os_name, arch in sorted(result.platforms))}"
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("references", nargs="+")
    parser.add_argument(
        "--same-digest",
        nargs=2,
        action="append",
        default=[],
        metavar=("LEFT", "RIGHT"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        results = {reference: verify_manifest(reference) for reference in args.references}
        for left, right in args.same_digest:
            left_result = results.get(left) or verify_manifest(left)
            right_result = results.get(right) or verify_manifest(right)
            if left_result.digest != right_result.digest:
                raise RuntimeError(
                    f"manifest digests differ: {left}={left_result.digest}, "
                    f"{right}={right_result.digest}"
                )
    except (json.JSONDecodeError, RuntimeError) as error:
        print(f"MANIFEST_VERIFY=FAIL {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

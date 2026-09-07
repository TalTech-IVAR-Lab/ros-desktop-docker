#!/usr/bin/env python3
"""Create the persistent ROS workspace without following untrusted paths."""

from __future__ import annotations

import argparse
import os
import pwd
import re
import sys
from pathlib import Path


WORKSPACE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class WorkspaceInitError(RuntimeError):
    """Raised when the persistent workspace cannot be initialized safely."""


def open_directory(path: Path) -> int:
    try:
        return os.open(path, DIRECTORY_FLAGS)
    except OSError as error:
        raise WorkspaceInitError(
            f"{path} must be an existing non-symlink directory: {error.strerror}"
        ) from error


def open_or_create_directory(
    parent_fd: int,
    name: str,
    *,
    display_path: Path,
    root_device: int,
    mode: int,
) -> int:
    try:
        os.mkdir(name, mode=mode, dir_fd=parent_fd)
    except FileExistsError:
        pass
    except OSError as error:
        raise WorkspaceInitError(
            f"cannot create {display_path}: {error.strerror}"
        ) from error

    try:
        directory_fd = os.open(name, DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        raise WorkspaceInitError(
            f"{display_path} must be a non-symlink directory: {error.strerror}"
        ) from error

    try:
        if os.fstat(directory_fd).st_dev != root_device:
            raise WorkspaceInitError(
                f"{display_path} must not cross a nested mount boundary"
            )
    except BaseException:
        os.close(directory_fd)
        raise

    return directory_fd


def initialize_workspace(
    config_root: Path,
    *,
    username: str,
    workspace_name: str = "ws_ivar_lab",
) -> None:
    if (
        workspace_name in {".", ".."}
        or not WORKSPACE_NAME.fullmatch(workspace_name)
    ):
        raise WorkspaceInitError(f"invalid ROS workspace name: {workspace_name!r}")

    try:
        account = pwd.getpwnam(username)
    except KeyError as error:
        raise WorkspaceInitError(f"desktop user does not exist: {username}") from error
    if os.geteuid() != account.pw_uid:
        raise WorkspaceInitError(
            f"initializer must run as {username} (uid {account.pw_uid}), "
            f"not uid {os.geteuid()}"
        )

    previous_umask = os.umask(0o022)
    directory_fds: list[int] = []
    try:
        root_fd = open_directory(config_root)
        directory_fds.append(root_fd)
        root_device = os.fstat(root_fd).st_dev
        current_path = config_root

        for component in ("ros", workspace_name, "src"):
            current_path /= component
            directory_fds.append(
                open_or_create_directory(
                    directory_fds[-1],
                    component,
                    display_path=current_path,
                    root_device=root_device,
                    mode=0o755,
                )
            )
    finally:
        for directory_fd in reversed(directory_fds):
            os.close(directory_fd)
        os.umask(previous_umask)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("/config"))
    parser.add_argument("--user", default=os.environ.get("DESKTOP_USER", "ivar"))
    parser.add_argument(
        "--workspace", default=os.environ.get("ROS_WS_NAME", "ws_ivar_lab")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        initialize_workspace(
            args.config_root,
            username=args.user,
            workspace_name=args.workspace,
        )
    except WorkspaceInitError as error:
        print(f"ROS workspace initialization refused: {error}", file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Static contract tests for the ROS LTS image roster."""

from __future__ import annotations

import json
import os
import pwd
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
WORKFLOW = ROOT / ".github" / "workflows" / "docker_build.yml"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"
README = ROOT / "README.md"
SMOKE_TEST = ROOT / "tests" / "smoke_image.sh"
MANIFEST_VERIFY = ROOT / "tests" / "verify_manifest.py"
ROOT_HOME_GUARD = ROOT / "files" / "etc" / "ros-desktop" / "root-home.sh"
WORKSPACE_INIT = (
    ROOT
    / "files"
    / "usr"
    / "local"
    / "libexec"
    / "taltech-init-ros-workspace.py"
)


class RosImageContractTests(unittest.TestCase):
    def test_dockerfile_frontend_is_digest_pinned(self) -> None:
        expected = (
            "# syntax=docker/dockerfile:1.7@"
            "sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e"
        )

        for path in (DOCKERFILE, ROOT / "Dockerfile_Noetic"):
            self.assertEqual(path.read_text().splitlines()[0], expected)

    def run_workspace_init(self, config_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_INIT),
                "--config-root",
                str(config_root),
                "--user",
                pwd.getpwuid(os.getuid()).pw_name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_workspace_init_with_name(
        self, config_root: Path, workspace_name: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_INIT),
                "--config-root",
                str(config_root),
                "--user",
                pwd.getpwuid(os.getuid()).pw_name,
                "--workspace",
                workspace_name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_workspace_initializer_creates_descriptor_rooted_directories(self) -> None:
        self.assertTrue(WORKSPACE_INIT.is_file(), WORKSPACE_INIT)
        self.assertTrue(WORKSPACE_INIT.stat().st_mode & stat.S_IXUSR)

        with tempfile.TemporaryDirectory() as directory:
            config_root = Path(directory) / "config"
            config_root.mkdir()

            result = self.run_workspace_init(config_root)

            self.assertEqual(0, result.returncode, result.stderr)
            for relative in ("ros", "ros/workspace", "ros/workspace/src"):
                path = config_root / relative
                self.assertTrue(path.is_dir(), path)
                self.assertFalse(path.is_symlink(), path)
                self.assertEqual(0o755, stat.S_IMODE(path.stat().st_mode))

    def test_workspace_initializer_rejects_symlinks_at_every_component(self) -> None:
        for symlink_component in ("ros", "workspace", "src"):
            with self.subTest(symlink_component=symlink_component):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    config_root = root / "config"
                    protected = root / "protected"
                    config_root.mkdir()
                    protected.mkdir()

                    parent = config_root
                    if symlink_component != "ros":
                        parent = config_root / "ros"
                        parent.mkdir()
                    if symlink_component == "src":
                        parent = parent / "workspace"
                        parent.mkdir()
                    (parent / symlink_component).symlink_to(
                        protected, target_is_directory=True
                    )

                    result = self.run_workspace_init(config_root)

                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("symlink", result.stderr.lower())
                    self.assertEqual([], list(protected.iterdir()))

    def test_workspace_initializer_does_not_repermission_existing_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_root = Path(directory) / "config"
            workspace_src = config_root / "ros" / "workspace" / "src"
            workspace_src.mkdir(parents=True)
            for path in (config_root / "ros", workspace_src.parent, workspace_src):
                path.chmod(0o700)

            result = self.run_workspace_init(config_root)

            self.assertEqual(0, result.returncode, result.stderr)
            for path in (config_root / "ros", workspace_src.parent, workspace_src):
                self.assertEqual(0o700, stat.S_IMODE(path.stat().st_mode))

    def test_workspace_initializer_rejects_special_directory_components(self) -> None:
        for workspace_name in (".", "..", "nested/workspace"):
            with self.subTest(workspace_name=workspace_name):
                with tempfile.TemporaryDirectory() as directory:
                    config_root = Path(directory) / "config"
                    config_root.mkdir()

                    result = self.run_workspace_init_with_name(
                        config_root, workspace_name
                    )

                    self.assertEqual(78, result.returncode)
                    self.assertIn("invalid ROS workspace name", result.stderr)

    def test_ros2_dockerfile_supports_only_valid_lts_pairs(self) -> None:
        content = DOCKERFILE.read_text()

        self.assertIn("ARG ROS_DISTRO=humble", content)
        self.assertIn("ARG UBUNTU_VERSION=22.04", content)
        self.assertIn("taltechivarlab/ubuntu-desktop:${UBUNTU_VERSION}", content)
        self.assertIn("humble:22.04", content)
        self.assertIn("jazzy:24.04", content)
        self.assertNotIn("noetic:20.04", content)

    def test_base_image_can_be_overridden_for_candidate_testing(self) -> None:
        ros2 = DOCKERFILE.read_text()
        noetic = (ROOT / "Dockerfile_Noetic").read_text()

        self.assertIn(
            "ARG BASE_IMAGE=taltechivarlab/ubuntu-desktop:${UBUNTU_VERSION}",
            ros2,
        )
        self.assertIn("FROM ${BASE_IMAGE}", ros2)
        self.assertIn(
            "ARG BASE_IMAGE=taltechivarlab/ubuntu-desktop:20.04",
            noetic,
        )
        self.assertIn("FROM ${BASE_IMAGE}", noetic)

    def test_noetic_pairs_private_xkbcommon_with_matching_x11_library(self) -> None:
        content = (ROOT / "Dockerfile_Noetic").read_text()

        self.assertIn("FROM ${BASE_IMAGE} AS xkbcommon_x11_builder", content)
        self.assertIn("ARG LIBXKBCOMMON_VERSION=1.5.0", content)
        self.assertIn(
            "sha256:560f11c4bbbca10f495f3ef7d3a6aa4ca62b4f8fb0b52e7d459d18a26e46e017",
            content,
        )
        self.assertIn("-Denable-x11=true", content)
        self.assertIn(
            "/opt/selkies-xkbcommon/lib/libxkbcommon-x11.so.0.0.0", content
        )
        self.assertNotIn(
            "COPY --from=xkbcommon_x11_builder "
            "/tmp/libxkbcommon-build/libxkbcommon.so",
            content,
        )

    def test_ros2_repository_setup_is_keyring_bound_and_vendored(self) -> None:
        content = DOCKERFILE.read_text()
        key = (ROOT / "files" / "ros.asc").read_text()

        self.assertIn("COPY files/ros.asc /usr/share/keyrings/ros-archive-keyring.asc", content)
        self.assertIn("signed-by=/usr/share/keyrings/ros-archive-keyring.asc", content)
        self.assertTrue(key.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"))
        self.assertTrue(key.rstrip().endswith("-----END PGP PUBLIC KEY BLOCK-----"))
        self.assertNotIn("apt-key", content)
        self.assertNotIn("raw.githubusercontent.com/ros/rosdistro", content)
        self.assertNotIn("curl |", content)
        self.assertNotIn("| bash", content)

        key_details = subprocess.run(
            ["gpg", "--show-keys", "--with-colons", str(ROOT / "files" / "ros.asc")],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        fingerprints = [
            line.split(":")[9]
            for line in key_details.splitlines()
            if line.startswith("fpr:")
        ]
        self.assertEqual(
            ["C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654"], fingerprints
        )

    def test_ros2_installs_available_desktop_motion_and_build_tools(self) -> None:
        content = DOCKERFILE.read_text()

        for token in (
            "ros-${ROS_DISTRO}-desktop",
            "ros-${ROS_DISTRO}-moveit",
            "python3-colcon-common-extensions",
            "python3-rosdep",
        ):
            self.assertIn(token, content)
        self.assertNotIn("industrial-core", content)

    def test_rosdep_cache_is_populated_for_the_runtime_desktop_user(self) -> None:
        ros2 = DOCKERFILE.read_text()
        noetic = (ROOT / "Dockerfile_Noetic").read_text()
        sources = "/etc/ros/rosdep/sources.list.d/20-default.list"
        update = 'runuser -u "${DESKTOP_USER}" -- env HOME=/config rosdep update'

        for content in (ros2, noetic):
            self.assertIn(f"if [ ! -e {sources} ]; then rosdep init; fi", content)
            self.assertIn(
                'install -d -o "${DESKTOP_USER}" -g "${DESKTOP_USER}" '
                "-m 0755 /config/.ros",
                content,
            )
            self.assertIn(update, content)
        self.assertNotIn("--include-eol-distros", ros2)
        self.assertIn(
            f"{update} --include-eol-distros",
            noetic,
        )

    def test_runtime_home_and_workspace_follow_the_published_base_contract(self) -> None:
        for dockerfile in (DOCKERFILE, ROOT / "Dockerfile_Noetic"):
            content = dockerfile.read_text()
            self.assertIn("HOME=/home/${DESKTOP_USER}", content)
            self.assertIn("ROS_WS_NAME=workspace", content)
            self.assertIn(
                "ROS_WS_PATH=/home/${DESKTOP_USER}/ros/workspace", content
            )

        for setup_path in (
            ROOT / "files" / "etc" / "ros-desktop" / "setup.bash",
            ROOT / "files" / "etc" / "ros-desktop" / "setup.zsh",
        ):
            setup = setup_path.read_text()
            self.assertIn('ROS_WS_NAME="${ROS_WS_NAME:-workspace}"', setup)
            self.assertIn(
                'ROS_WS_PATH="${ROS_WS_PATH:-/home/${DESKTOP_USER:-ivar}/ros/${ROS_WS_NAME}}"',
                setup,
            )

        init_run = (
            ROOT
            / "files"
            / "etc"
            / "s6-overlay"
            / "s6-rc.d"
            / "init-ros-workspace"
            / "run"
        ).read_text()
        self.assertIn('--workspace "${ROS_WS_NAME:-workspace}"', init_run)
        self.assertNotIn("ws_ivar_lab", "\n".join(
            path.read_text()
            for path in (
                DOCKERFILE,
                ROOT / "Dockerfile_Noetic",
                ROOT / "README.md",
                ROOT / "tests" / "smoke_image.sh",
                ROOT / "files" / "etc" / "ros-desktop" / "setup.bash",
                ROOT / "files" / "etc" / "ros-desktop" / "setup.zsh",
                ROOT / "files" / "etc" / "s6-overlay" / "s6-rc.d" / "init-ros-workspace" / "run",
                WORKSPACE_INIT,
            )
        ))

    def test_derived_images_replace_inherited_oci_revision_metadata(self) -> None:
        for dockerfile in (DOCKERFILE, ROOT / "Dockerfile_Noetic"):
            content = dockerfile.read_text()
            self.assertIn('org.opencontainers.image.revision="${VERSION}"', content)

    def test_shell_setup_and_workspace_are_runtime_safe(self) -> None:
        content = DOCKERFILE.read_text()
        init_run = ROOT / "files" / "etc" / "s6-overlay" / "s6-rc.d" / "init-ros-workspace" / "run"
        setup_bash = ROOT / "files" / "etc" / "ros-desktop" / "setup.bash"
        setup_zsh = ROOT / "files" / "etc" / "ros-desktop" / "setup.zsh"

        self.assertIn("/etc/bash.bashrc", content)
        self.assertIn("/etc/zsh/zshrc", content)
        for path in (init_run, setup_bash, setup_zsh):
            self.assertTrue(path.is_file(), path)
        self.assertTrue(init_run.stat().st_mode & stat.S_IXUSR)
        self.assertIn("taltech-init-ros-workspace.py", init_run.read_text())
        self.assertIn("install/setup.bash", setup_bash.read_text())
        self.assertIn("devel/setup.bash", setup_bash.read_text())
        self.assertIn("devel/setup.zsh", setup_zsh.read_text())
        self.assertNotIn("ROS_DOMAIN_ID=", content)

    def test_privileged_shells_never_source_writable_workspace_overlays(self) -> None:
        for shell in ("bash", "zsh"):
            with self.subTest(shell=shell):
                setup = (
                    ROOT / "files" / "etc" / "ros-desktop" / f"setup.{shell}"
                ).read_text()
                uid_lookup = 'id -u "${DESKTOP_USER:-ivar}"'
                guard = (
                    "if [[ -n ${_taltech_desktop_uid} "
                    "&& ${EUID} -eq ${_taltech_desktop_uid} ]]; then"
                )
                overlay = f'"${{ROS_WS_PATH}}/install/setup.{shell}"'

                self.assertIn(uid_lookup, setup)
                self.assertIn(guard, setup)
                self.assertIn(overlay, setup)
                self.assertLess(setup.index(guard), setup.index(overlay))
                self.assertIn("fi\n", setup[setup.index(overlay) :])

    def test_privileged_shells_reset_the_inherited_persistent_home(self) -> None:
        self.assertTrue(ROOT_HOME_GUARD.is_file(), ROOT_HOME_GUARD)
        guard = ROOT_HOME_GUARD.read_text()
        self.assertIn('"$(id -u)" -eq 0', guard)
        self.assertIn("export HOME=/root", guard)
        self.assertNotIn('"${HOME:-}"', guard)

        for dockerfile in (DOCKERFILE, ROOT / "Dockerfile_Noetic"):
            content = dockerfile.read_text()
            for startup_file in (
                "/etc/profile",
                "/etc/bash.bashrc",
                "/etc/zsh/zshenv",
            ):
                token = f"/etc/ros-desktop/root-home.sh\\n' | cat - {startup_file}"
                self.assertIn(token, content)

        for setup_path in (
            ROOT / "files" / "etc" / "ros-desktop" / "setup.bash",
            ROOT / "files" / "etc" / "ros-desktop" / "setup.zsh",
        ):
            setup = setup_path.read_text()
            allowlist = '"noetic"|"humble"|"jazzy"'
            self.assertIn(allowlist, setup)
            self.assertLess(setup.index(allowlist), setup.index("/opt/ros/"))

    def test_workspace_init_uses_the_base_desktop_user(self) -> None:
        init_run = (
            ROOT
            / "files"
            / "etc"
            / "s6-overlay"
            / "s6-rc.d"
            / "init-ros-workspace"
            / "run"
        ).read_text()

        self.assertIn('desktop_user="${DESKTOP_USER:-ivar}"', init_run)
        self.assertIn('exec s6-setuidgid "${desktop_user}"', init_run)
        self.assertIn("/usr/local/libexec/taltech-init-ros-workspace.py", init_run)
        self.assertIn('--user "${desktop_user}"', init_run)
        self.assertNotIn("install -d", init_run)
        self.assertNotIn("os.fchown", WORKSPACE_INIT.read_text())
        self.assertNotIn("os.fchmod", WORKSPACE_INIT.read_text())

        docs = README.read_text()
        self.assertIn("does not unlock the `ivar` account", docs)
        self.assertIn("ssh ivar@HOST", docs)
        self.assertNotIn("passwd ivar", docs)

    def test_workspace_init_uses_a_base_agnostic_s6_boundary(self) -> None:
        dependencies = (
            ROOT
            / "files"
            / "etc"
            / "s6-overlay"
            / "s6-rc.d"
            / "init-ros-workspace"
            / "dependencies.d"
        )

        self.assertTrue((dependencies / "init-os-end").is_file())
        self.assertFalse((dependencies / "init-desktop-config").exists())

    def test_ci_builds_noetic_humble_and_jazzy_for_both_architectures(self) -> None:
        content = WORKFLOW.read_text()

        rows = re.findall(
            r"- distro: (\w+)\s+"
            r"ubuntu: ([0-9.]+)\s+"
            r"dockerfile: (\S+)\s+"
            r"base_image: (\S+)",
            content,
        )
        self.assertEqual(
            [
                (
                    "noetic",
                    "20.04",
                    "Dockerfile_Noetic",
                    "taltechivarlab/ubuntu-desktop@sha256:c95f92c071b6a0611bd2b6023623ec7b92b0896db00bf28db0e6c8e60599cb06",
                ),
                (
                    "humble",
                    "22.04",
                    "Dockerfile",
                    "taltechivarlab/ubuntu-desktop@sha256:40ffbbb5558dc32031fa248f6dc8502a050f34722d3b24e9fdcb01260edd6576",
                ),
                (
                    "jazzy",
                    "24.04",
                    "Dockerfile",
                    "taltechivarlab/ubuntu-desktop@sha256:02cd05a8bbf5aa93a77e44d109f6610efde2416143e3be26f434cd36cf72bfcf",
                ),
            ],
            rows,
        )
        self.assertIn("linux/amd64,linux/arm64", content)
        self.assertIn("BASE_IMAGE=${{ matrix.base_image }}", content)
        self.assertIn("ROS_DISTRO=${{ matrix.distro }}", content)
        self.assertIn("UBUNTU_VERSION=${{ matrix.ubuntu }}", content)
        self.assertNotIn("lyrical", content.lower())
        self.assertNotRegex(content, r"(?m)^\s+schedule:")

    def test_ci_runs_contract_tests(self) -> None:
        content = WORKFLOW.read_text()

        self.assertIn("python3 -B -m unittest -v tests.test_image_contract", content)

    def test_ci_starts_and_smoke_tests_each_ros_image(self) -> None:
        workflow = WORKFLOW.read_text()

        self.assertTrue(SMOKE_TEST.is_file(), SMOKE_TEST)
        self.assertTrue(SMOKE_TEST.stat().st_mode & stat.S_IXUSR, SMOKE_TEST)
        self.assertIn("platforms: linux/amd64", workflow)
        self.assertIn("platforms: linux/arm64", workflow)
        self.assertIn("load: true", workflow)
        self.assertIn("tests/smoke_image.sh", workflow)
        self.assertIn("- name: Smoke-test exact pushed candidate", workflow)
        self.assertIn(
            'tests/smoke_image.sh "${candidate_ref}" ${{ matrix.distro }} linux/amd64',
            workflow,
        )
        self.assertIn(
            'tests/smoke_image.sh "${candidate_ref}" ${{ matrix.distro }} linux/arm64',
            workflow,
        )

        smoke = SMOKE_TEST.read_text()
        for token in (
            "roscore",
            "rostopic",
            "ros2 run demo_nodes_cpp talker",
            "ros2 topic echo",
            "rosdep db",
            "docker volume create",
            "docker rm -f",
            'docker exec -u "${desktop_user}"',
            "ROS_OVERLAY_SENTINEL",
            "ROS_DOTFILE_SENTINEL",
            'test "${HOME}" = /root',
            "moveit_ros_move_group",
            "rviz",
            "taltech-init-ros-workspace.py",
        ):
            self.assertIn(token, smoke)
        self.assertNotIn("docker restart", smoke)
        self.assertIn(
            "rostopic echo -n 1 /ci_chatter | grep -F hello-noetic", smoke
        )
        self.assertNotIn(
            "rostopic echo -n 1 /ci_chatter std_msgs/String", smoke
        )
        self.assertIn(
            "/var/lib/taltech-desktop/ssh/ssh_host_ed25519_key.pub", smoke
        )
        self.assertIn('xdpyinfo -display "${DISPLAY:-:1}"', smoke)
        self.assertIn('dpkg --print-architecture', smoke)
        self.assertIn('linux/amd64) expected_arch=amd64', smoke)
        self.assertIn('linux/arm64) expected_arch=arm64', smoke)
        self.assertIn('test "${HOME}" = "/home/${DESKTOP_USER}"', smoke)
        self.assertIn('test "${ROS_WS_NAME}" = workspace', smoke)
        self.assertIn(
            'test "${ROS_WS_PATH}" = "/home/${DESKTOP_USER}/ros/workspace"', smoke
        )
        self.assertIn('readlink "/home/${desktop_user}"', smoke)
        self.assertIn('/config/ros/workspace/src', smoke)
        self.assertIn('/home/${desktop_user}/ros/workspace/src', smoke)
        self.assertIn(
            "check_ros_communication\nwait_for_display\ncheck_rviz_stability", smoke
        )

    def test_ci_promotes_only_after_all_candidates_pass(self) -> None:
        workflow = WORKFLOW.read_text()
        publish_condition = (
            "github.event_name == 'push' && github.ref == 'refs/heads/main'"
        )
        candidate = "candidate-${{ github.sha }}-${{ matrix.distro }}"

        self.assertIn(f"push: ${{{{ {publish_condition} }}}}", workflow)
        self.assertIn(candidate, workflow)
        self.assertIn("id: candidate", workflow)
        self.assertIn("steps.candidate.outputs.digest", workflow)
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            workflow,
        )
        self.assertIn("  promote:\n", workflow)
        promotion = workflow[workflow.index("  promote:\n") :]
        self.assertIn("needs: build", promotion)
        self.assertIn(f"if: {publish_condition}", promotion)
        self.assertIn("group: ros-desktop-production", promotion)
        self.assertIn("cancel-in-progress: false", promotion)
        self.assertIn(
            "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
            promotion,
        )
        self.assertIn("tests/verify_manifest.py", promotion)
        for tag in ("noetic", "humble", "jazzy", "latest"):
            self.assertIn(f"taltechivarlab/ros-desktop:{tag}", promotion)
        for distro in ("noetic", "humble", "jazzy"):
            self.assertIn(f'taltechivarlab/ros-desktop@${{{distro}_digest}}', promotion)
            self.assertIn(
                f"--same-digest taltechivarlab/ros-desktop:{distro} "
                f'taltechivarlab/ros-desktop@${{{distro}_digest}}',
                promotion,
            )
        self.assertNotIn("candidate-${GITHUB_SHA}", promotion)

        build_job = workflow[: workflow.index("  promote:\n")]
        for mutable_tag in ("noetic", "humble", "jazzy", "latest"):
            self.assertNotIn(
                f"taltechivarlab/ros-desktop:{mutable_tag}", build_job
            )

    def test_manifest_verifier_requires_both_supported_architectures(self) -> None:
        self.assertTrue(MANIFEST_VERIFY.is_file(), MANIFEST_VERIFY)

        def run_verifier(manifest: dict[str, object]) -> subprocess.CompletedProcess[str]:
            with tempfile.TemporaryDirectory() as directory:
                fake_docker = Path(directory) / "docker"
                fake_docker.write_text(
                    "#!/bin/sh\nprintf '%s\\n' \"${FAKE_DOCKER_MANIFEST}\"\n"
                )
                fake_docker.chmod(0o755)
                return subprocess.run(
                    [sys.executable, str(MANIFEST_VERIFY), "example.invalid/test:tag"],
                    check=False,
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "PATH": f"{directory}:{os.environ['PATH']}",
                        "FAKE_DOCKER_MANIFEST": json.dumps(manifest),
                    },
                )

        valid = {
            "digest": "sha256:" + "a" * 64,
            "manifests": [
                {"platform": {"os": "linux", "architecture": "amd64"}},
                {"platform": {"os": "linux", "architecture": "arm64"}},
                {"platform": {"os": "unknown", "architecture": "unknown"}},
            ],
        }
        accepted = run_verifier(valid)
        self.assertEqual(0, accepted.returncode, accepted.stderr)
        self.assertIn("MANIFEST_VERIFY=PASS", accepted.stdout)

        invalid = {
            "digest": "sha256:" + "b" * 64,
            "manifests": [
                {"platform": {"os": "linux", "architecture": "amd64"}},
            ],
        }
        rejected = run_verifier(invalid)
        self.assertEqual(1, rejected.returncode)
        self.assertIn("MANIFEST_VERIFY=FAIL", rejected.stderr)

    def test_ci_actions_are_immutable_and_automatically_maintained(self) -> None:
        workflow = WORKFLOW.read_text()
        action_refs = re.findall(r"^\s*uses:\s*([^#\s]+)", workflow, re.MULTILINE)
        versioned_action_refs = re.findall(
            r"^\s*uses:\s*[^#\s]+\s+#\s+v\d+\s*$", workflow, re.MULTILINE
        )

        self.assertTrue(action_refs)
        for action_ref in action_refs:
            self.assertRegex(action_ref, r"^[^@\s]+@[0-9a-f]{40}$")
        self.assertEqual(len(action_refs), len(versioned_action_refs))
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("timeout-minutes: 360", workflow)
        self.assertIn("BUILD_DATE=${{ env.BUILD_DATE }}", workflow)
        self.assertIn("VERSION=${{ github.sha }}", workflow)

        publish_condition = "github.event_name == 'push' && github.ref == 'refs/heads/main'"

        def step(name: str) -> str:
            start = workflow.index(f"      - name: {name}\n")
            end = workflow.find("\n      - name:", start + 1)
            return workflow[start:] if end < 0 else workflow[start:end]

        self.assertIn(
            f"if: {publish_condition}",
            step("Login to Docker Hub for candidate push"),
        )
        self.assertIn(
            f"push: ${{{{ {publish_condition} }}}}",
            step("Build multi-architecture candidate"),
        )
        self.assertIn(
            f"if: {publish_condition}",
            workflow[workflow.index("  promote:\n") :],
        )

        dependabot = DEPENDABOT.read_text()
        self.assertIn('package-ecosystem: "github-actions"', dependabot)
        self.assertIn('interval: "monthly"', dependabot)

    def test_noetic_is_a_first_class_discoverable_image(self) -> None:
        noetic = (ROOT / "Dockerfile_Noetic").read_text()
        docs = README.read_text()
        noetic_rows = [line for line in docs.splitlines() if "ROS Noetic" in line]

        self.assertIn("ros-noetic-desktop-full", noetic)
        self.assertTrue(noetic_rows)
        self.assertTrue(all("legacy" not in line.lower() for line in noetic_rows))
        self.assertIn("`noetic`", docs)
        self.assertIn("humble", docs.lower())
        self.assertIn("jazzy", docs.lower())
        self.assertNotIn("lyrical", docs.lower())

    def test_noetic_build_uses_the_vendored_key_and_runtime_workspace(self) -> None:
        content = (ROOT / "Dockerfile_Noetic").read_text()

        self.assertIn("COPY files/ros.asc /usr/share/keyrings/ros-archive-keyring.asc", content)
        self.assertIn("signed-by=/usr/share/keyrings/ros-archive-keyring.asc", content)
        self.assertIn("COPY files/etc/ros-desktop/ /etc/ros-desktop/", content)
        self.assertIn("COPY files/etc/s6-overlay/ /etc/s6-overlay/", content)
        self.assertNotIn("apt-key", content)
        self.assertNotIn("curl", content)

    def test_documented_ports_match_the_base_image(self) -> None:
        docs = README.read_text()

        self.assertIn("3001:3001", docs)
        self.assertIn("2222:22", docs)
        self.assertNotIn("3390:3389", docs)
        self.assertNotIn("default password", docs.lower())

    def test_all_ros_images_document_the_selkies_base_contract(self) -> None:
        docs = README.read_text()

        self.assertIn("All three images use Selkies", docs)
        self.assertIn("https://HOST:3001/", docs)
        self.assertIn("CUSTOM_USER", docs)
        self.assertIn("PASSWORD_FILE", docs)
        self.assertIn("key-only SSH", docs)
        self.assertNotIn("XRDP", docs)
        self.assertNotIn("RDP_PORT", docs)
        self.assertIn("configured for 1920×1080 at up to 60 FPS", docs)
        self.assertNotIn("desktop runs at 1920×1080 and 60 FPS", docs)


if __name__ == "__main__":
    unittest.main()

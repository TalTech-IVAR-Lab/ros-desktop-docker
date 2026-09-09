# ROS Desktop Docker

[![ROS version](https://img.shields.io/badge/ROS-Noetic%20%7C%20Humble%20%7C%20Jazzy-informational?logo=ros)](https://docs.ros.org/)
[![Ubuntu version](https://img.shields.io/badge/Ubuntu-20.04%20%7C%2022.04%20%7C%2024.04-informational?logo=ubuntu)](https://releases.ubuntu.com/)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/TalTech-IVAR-Lab/ros-desktop-docker/docker_build.yml?branch=main&logo=GitHub)](https://github.com/TalTech-IVAR-Lab/ros-desktop-docker/actions)
[![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/taltechivarlab/ros-desktop?logo=docker)](https://hub.docker.com/r/taltechivarlab/ros-desktop)

> Based on the `taltechivarlab/ubuntu-desktop:20.04`, `:22.04`, and `:24.04` images by [TalTech IVAR Lab][taltech_ivar_lab_github]

Dockerized ROS Desktop environment for development and experimentation used by [TalTech IVAR Lab][taltech_ivar_lab].

## Why and how

Learn why this project was created and how it is useful by reading our [Motivation doc][docs_motivation].

## What's included

In addition to the Ubuntu desktop base, all images include a persistent
workspace and automatic ROS environment sourcing. The ROS 2 images include:

- Full ROS 2 Desktop installation
- MoveIt 2, including the Pilz industrial motion planner used by the XRM demo
- Colcon, vcstool, standard build tooling, and a populated rosdep cache
- Persistent empty colcon workspace at `/home/ivar/ros/workspace`
- Automatic ROS and workspace sourcing in interactive Bash and Zsh shells
- `ROS_WS_NAME=workspace` and `ROS_WS_PATH=/home/ivar/ros/workspace`

The base image exposes the conventional home `/home/ivar`, backed by the
persistent `/config` volume. Thus the workspace is stored persistently at
`/config/ros/workspace` while tools and shells use its normal home-directory
path.

The Noetic image includes ROS Desktop Full, MoveIt, ROS-Industrial Core,
catkin-tools, rosdep, rosinstall, and wstool. Noetic remains directly
discoverable under the `noetic` tag, while its upstream end-of-life status is
stated explicitly.

The ROS 2 repositories do not publish an ABB driver binary for Humble or Jazzy.
ABB packages will be imported and built from source in the persistent workspace
once their exact revisions are selected.

For the full package lists, see `Dockerfile` and `Dockerfile_Noetic` in this
repository.

## Image roster

| ROS | Ubuntu base | Tag | Status |
|---|---|---|---|
| ROS 2 Jazzy | Ubuntu 24.04 Noble | `jazzy`, `latest` | Maintained LTS |
| ROS 2 Humble | Ubuntu 22.04 Jammy | `humble` | Maintained LTS |
| ROS Noetic | Ubuntu 20.04 Focal | `noetic` | ROS 1; upstream EOL, active compatibility build |

Release CI intentionally manages `latest` as the ROS 2 Jazzy alias. The first
coordinated promotion changes it from the former ROS Noetic image; existing
users should pin `noetic` before updating. Moving between those tags also
changes the ROS major version and Ubuntu base.

`Dockerfile_Noetic` is an active CI target. The main `Dockerfile` intentionally
accepts only the supported ROS 2 pairs: Humble/Jammy and Jazzy/Noble.

All three images use Selkies in the browser through their Ubuntu desktop
bases. They share the same HTTPS, key-only SSH, and `/config` persistence
contract.

## Usage

### Quick start: Selkies

Create a mode-`0600` file containing a web password of at least 12 characters,
then launch the required ROS tag on a trusted network or VPN. This example uses
Humble; replace the tag with `noetic` or `jazzy` as needed:

```bash
docker run -d \
  --name=ros-desktop-humble \
  --gpus=all \
  --device=/dev/dri:/dev/dri \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Europe/Tallinn \
  -e CUSTOM_USER=taltech \
  -e PASSWORD_FILE=/run/secrets/selkies-password \
  -p 3001:3001 `# https` \
  -p 2222:22 `# ssh` \
  -v "$HOME/.taltech-selkies-password:/run/secrets/selkies-password:ro" \
  -v ros-desktop-config:/config \
  -v ros-desktop-state:/var/lib/taltech-desktop \
  --shm-size="1gb" \
  --restart unless-stopped \
  taltechivarlab/ros-desktop:humble
```

Open `https://HOST:3001/`. The desktop is configured for 1920×1080 at up to 60 FPS;
actual negotiated encoding and frame rate depend on the browser, GPU, and network.
SSH is key-only SSH: add public keys to `/config/.ssh/authorized_keys`. Web
authentication does not unlock the `ivar` account. Omit `--gpus=all` on
non-NVIDIA hosts. Connect with `ssh ivar@HOST -p 2222`.

Interactive shells source the immutable ROS installation automatically. The
writable workspace overlay is sourced only for unprivileged shells, so a root
maintenance shell never executes workspace-controlled startup code.

Keep HTTPS and SSH on a trusted LAN or VPN; do not expose them directly
to the Internet.

### ROS 2 networking

Bridge networking is fine for self-contained development, but ROS 2 DDS
discovery on the lab LAN may require host networking, macvlan, or an explicit
DDS peer configuration. The first `lab-ros` Jazzy probe will use host
networking and move SSH away from the host's port. Selkies continues to serve
HTTPS on port 3001:

```bash
docker run -d \
  --name=ros-desktop-jazzy-lab \
  --network host \
  -e SSH_PORT=2222 \
  -e CUSTOM_USER=taltech \
  -e PASSWORD_FILE=/run/secrets/selkies-password \
  -e ROS_DOMAIN_ID=<matching-lab-domain> \
  -v "$HOME/.taltech-selkies-password:/run/secrets/selkies-password:ro" \
  -v ros-desktop-config:/config \
  -v ros-desktop-state:/var/lib/taltech-desktop \
  taltechivarlab/ros-desktop:jazzy
```

`ROS_DOMAIN_ID` is deliberately a runtime setting; the image does not assume
the lab's DDS domain or discovery topology.

### Advanced usage

For more advanced use cases, such as opening additional ports and enabling hardware graphics acceleration, please refer to the [Advanced Usage][docs_advanced_usage] doc.

## Building locally

Build any supported ROS image:

```bash
docker build -f Dockerfile_Noetic -t taltechivarlab/ros-desktop:noetic .
docker build --build-arg ROS_DISTRO=humble --build-arg UBUNTU_VERSION=22.04 \
  -t taltechivarlab/ros-desktop:humble .
docker build --build-arg ROS_DISTRO=jazzy --build-arg UBUNTU_VERSION=24.04 \
  -t taltechivarlab/ros-desktop:jazzy .
```

Pull requests build and start amd64 and arm64 images for every ROS distribution,
exercise authenticated Selkies startup, user-context ROS communication, RViz,
shell privilege boundaries, rosdep, MoveIt, and volume-backed recreation, then
compile the dual-architecture candidates. A push to `main` repeats the runtime
checks against the exact pushed manifest digests. It promotes `noetic`,
`humble`, `jazzy`, and `latest` only after all candidates pass, then reads every
public tag back and verifies it against the tested digest.

In case you want to build a multi-architecture image (e.g. to run it on a Raspberry Pi), you can build for multiple platforms using the [Docker Buildx][docker_buildx] backend (by specifying them in the `--platform` flag):

```bash
docker buildx build --platform=linux/amd64,linux/arm64 \
  --build-arg ROS_DISTRO=jazzy --build-arg UBUNTU_VERSION=24.04 \
  -t taltechivarlab/ros-desktop:jazzy \
  --output type=oci,dest=ros-desktop-jazzy.tar .
```

## Contributing

The project is in early stages of development, so we are not yet accepting contributions from outside our university organization. 


[taltech_ivar_lab]: https://ivar.taltech.ee/
[taltech_ivar_lab_github]: https://github.com/TalTech-IVAR-Lab
[docker_buildx]: https://www.docker.com/blog/how-to-rapidly-build-multi-architecture-images-with-buildx/#

[docs_motivation]: https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker/blob/main/docs/MOTIVATION.md
[docs_advanced_usage]: https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker/blob/main/docs/ADVANCED_USAGE.md

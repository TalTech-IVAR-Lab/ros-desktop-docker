# ROS Desktop Docker

[![Ubuntu version](https://img.shields.io/badge/Ubuntu-20.04-informational?logo=ubuntu)](https://releases.ubuntu.com/focal/)
[![ROS version](https://img.shields.io/badge/ROS-noetic-informational?logo=ros)](http://wiki.ros.org/noetic)
[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/TalTech-IVAR-Lab/ros-desktop-docker/docker_build.yml?branch=main&logo=GitHub)](https://github.com/TalTech-IVAR-Lab/ros-desktop-docker/actions)
[![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/taltechivarlab/ros-desktop?logo=docker)](https://hub.docker.com/r/taltechivarlab/ros-desktop)

> Based on the [taltechivarlab/ubuntu-desktop:20.04][ubuntu_desktop_github] image by [TalTech IVAR Lab][taltech_ivar_lab_github]

Dockerized ROS Desktop environment for development and experimentation used by [TalTech IVAR Lab][taltech_ivar_lab].

## Why and how

Learn why this project was created and how it is useful by reading our [Motivation doc][docs_motivation].

## What's included

In addition to what is already in [taltechivarlab/ubuntu-desktop:20.04][ubuntu_desktop_github], this image adds modifications required for ROS development:

- Full [ROS Noetic Desktop][ros_noetic] installation
- Preconfigured empty [catkin] workspace at `/config/ros/ws_ivar_lab`
- Updated `.bashrc` and `.zshrc` (for the default _abc_ user):
  - ROS is sourced automatically
  - Default workspace (`ws_ivar_lab`) is sourced automatically
  - Predefined environment variables:
    - `ROS_WS_NAME="ws_ivar_lab"`
    - `ROS_WS_PATH="/config/ros/ws_ivar_lab"`
- Desktop look:
  ![desktop screenshot from ros desktop docker](https://raw.githubusercontent.com/TalTech-IVAR-Lab/ros-desktop-docker/main/docs/images/desktop.png "Default desktop environment in this Docker image")

For the full list of preinstalled ROS packages please refer to this repo's [Dockerfile].

## Usage

### Quick start

Once you have [installed Docker][docs_install_docker], to launch the container directly:

```bash
docker run -d \
  --name=ros-desktop \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Europe/Tallinn \
  -p 3390:3390 `# rdp` \
  -p 2222:2222 `# ssh` \
  -p 11311:11311 `# ros master node` \
  --shm-size="1gb" \
  --security-opt seccomp=unconfined \
  --restart unless-stopped \
  taltechivarlab/ros-desktop:noetic
```

Once the container has started, you must `ssh` into it (default password is `abc`):

```bash
ssh abc@localhost -p 2222
```

...and change _abc_ user's default password following the displayed instructions.

After that, you can use login _abc_ and the newly set password to log in to the container using any remote desktop client.

> ???? When inside the container, you can switch your default shell to [Zsh][presto-prezto_demo] by running the following
> command in the terminal:
>
> ```bash
> sudo usermod --shell $(command -v zsh) abc
> ```

> ??? You can [stop][docker_stop] and [restart][docker_start] the created container from Docker without losing your data.
> It is equivalent to system shutdown from the containerized Ubuntu's point of view. However, keep in mind that [_deleting_][docker_rm] your container will destroy all the data and software contained inside.

> ???? If you intend to connect to your ROS nodes from outside this container, you will likely need to open more ports. To learn how to do that, refer to the advanced usage section below.

### Advanced usage

For more advanced use cases, such as opening additional ports and enabling hardware graphics acceleration, please refer to the [Advanced Usage][docs_advanced_usage] doc.

## Building locally

If you want to build this image locally instead of pulling it from [Dockerhub], clone this repository and run the build:

```bash
docker build -t taltechivarlab/ros-desktop:noetic .
```

In case you want to build a multi-architecture image (e.g. to run it on a Raspberry Pi), you can build for multiple platforms using the [Docker Buildx][docker_buildx] backend (by specifying them in the `--platform` flag):

```bash
docker buildx build --platform=linux/amd64,linux/arm64 -t taltechivarlab/ros-desktop:noetic --output=oci .
```

## Contributing

The project is in early stages of development, so we are not yet accepting contributions from outside our university organization. 


[taltech_ivar_lab]: https://ivar.taltech.ee/
[ubuntu_desktop_github]: https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker
[taltech_ivar_lab_github]: https://github.com/TalTech-IVAR-Lab
[ros_noetic]: http://wiki.ros.org/noetic
[ros_desktop_github]: https://github.com/TalTech-IVAR-Lab/ros-desktop-docker
[catkin]: http://wiki.ros.org/catkin
[rdesktop_github_hardware_acceleration]: https://github.com/linuxserver/docker-rdesktop#hardware-acceleration-ubuntu-container-only
[Dockerhub]: https://hub.docker.com/
[docker_buildx]: https://www.docker.com/blog/how-to-rapidly-build-multi-architecture-images-with-buildx/#
[dockerfile]: https://github.com/TalTech-IVAR-Lab/ros-desktop-docker/blob/main/Dockerfile
[docker_stop]: https://docs.docker.com/engine/reference/commandline/stop/
[docker_start]: https://docs.docker.com/engine/reference/commandline/start/
[docker_rm]: https://docs.docker.com/engine/reference/commandline/rm/
[update_docker_port_in_flight]: https://www.baeldung.com/linux/assign-port-docker-container#reconfigure-docker-in-flight
[update_docker_port_in_flight_stackoverflow]: https://stackoverflow.com/a/38783433
[docker_network_host]: https://docs.docker.com/network/host/

[docs_motivation]: https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker/blob/main/docs/MOTIVATION.md
[docs_advanced_usage]: https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker/blob/main/docs/ADVANCED_USAGE.md
[docs_install_docker]: https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker/blob/main/docs/INSTALLING_DOCKER.md

# ROS Desktop Docker

[![Ubuntu version](https://img.shields.io/badge/Ubuntu-20.04-informational?logo=ubuntu)](https://releases.ubuntu.com/focal/)
[![ROS version](https://img.shields.io/badge/ROS-noetic-informational?logo=ros)](http://wiki.ros.org/noetic)
[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/TalTech-IVAR-Lab/ros-desktop-docker/Docker%20Build?logo=github)](https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker/actions)
[![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/taltechivarlab/ros-desktop?logo=docker)](https://hub.docker.com/r/taltechivarlab/ubuntu-desktop)

> Based on the [taltechivarlab/ubuntu-desktop:20.04][ubuntu_desktop_github] image by [TalTech IVAR Lab][taltech_ivar_lab_github]

Dockerized ROS Desktop environment for development and experimentation used by [TalTech IVAR Lab][taltech_ivar_lab].

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

To launch the container directly:

```bash
docker run -d \
  --name=ros-desktop \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Europe/London \
  -p 3389:3389 `#rdp` \
  -p 2222:22 `#ssh` \
  -p 10000:10000 `#ros master node` \
  --shm-size="1gb" \
  --security-opt seccomp=unconfined \
  --restart unless-stopped \
  -e NVIDIA_VISIBLE_DEVICES=all taltechivarlab/ros-desktop:noetic
```

Once the container has started, you must `ssh` into it (default password is `abc`):

```bash
ssh abc@localhost -p 2222
```

...and change _abc_ user's default password following the displayed instructions.

After that, you can use login _abc_ and the newly set password to login to the container using any remote desktop client.

> ☝ You can [stop][docker_stop] and [restart][docker_start] the created container from Docker without losing your data. It is equivalent to system shutdown from the containerized Ubuntu's point of view. However, keep in mind that [_deleting_][docker_rm] your container will destroy all the data and software contained inside.

> 💡 If you intend to connect to your ROS nodes from outside this container, you will likely need to open more ports.
> 
> The port mappings are specified with the initial `docker run` call, but you cannot delete and recreate the container without losing the data inside. Instead, please follow this [answer from Stackoverflow][update_docker_port_in_flight_stackoverflow] or this [article][update_docker_port_in_flight] to modify the port mappings of already running container without destroying it.
> 
> Alternatively, you can start the container with `--network host` flag. This will make all ports of the container available to the host network, but [only works on Linux hosts][docker_network_host].

## Building locally

If you want to build this image locally instead of pulling it from [Dockerhub], clone this repository and run the build:

```bash
docker build -t taltechivarlab/ros-desktop:noetic .
```

In case you want to build a multi-architecture image (e.g. to run it on a Raspberry Pi), you can build for multiple platforms using the [Docker Buildx][docker_buildx] backend (by specifying them in the `--platform` flag):

```bash
docker buildx build --platform=linux/amd64,linux/arm64 -t taltechivarlab/ros-desktop:noetic --output=oci .
```


[taltech_ivar_lab]: https://ivar.taltech.ee/
[ubuntu_desktop_github]: https://github.com/TalTech-IVAR-Lab/ubuntu-desktop-docker
[taltech_ivar_lab_github]: https://github.com/TalTech-IVAR-Lab
[ros_noetic]: http://wiki.ros.org/noetic
[ros_desktop_github]: https://github.com/TalTech-IVAR-Lab/ros-desktop-docker
[catkin]: http://wiki.ros.org/catkin
[rdesktop_github_hardware_acceleration]: https://github.com/linuxserver/docker-rdesktop#hardware-acceleration-ubuntu-container-only
[Dockerhub]: https://hub.docker.com/
[docker_buildx]: https://www.docker.com/blog/how-to-rapidly-build-multi-architecture-images-with-buildx/#
[dockerfile]: https://raw.githubusercontent.com/TalTech-IVAR-Lab/ros-desktop-docker/main/Dockerfile
[docker_stop]: https://docs.docker.com/engine/reference/commandline/stop/
[docker_start]: https://docs.docker.com/engine/reference/commandline/start/
[docker_rm]: https://docs.docker.com/engine/reference/commandline/rm/
[update_docker_port_in_flight]: https://www.baeldung.com/linux/assign-port-docker-container#reconfigure-docker-in-flight
[update_docker_port_in_flight_stackoverflow]: https://stackoverflow.com/a/38783433
[docker_network_host]: https://docs.docker.com/network/host/

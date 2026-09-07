# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG UBUNTU_VERSION=22.04
ARG BASE_IMAGE=taltechivarlab/ubuntu-desktop:${UBUNTU_VERSION}
FROM ${BASE_IMAGE}

ARG BUILD_DATE
ARG VERSION
ARG UBUNTU_VERSION
ARG ROS_DISTRO=humble

LABEL org.opencontainers.image.title="TalTech IVAR Lab ROS Desktop" \
      org.opencontainers.image.description="ROS 2 ${ROS_DISTRO} desktop development environment" \
      org.opencontainers.image.source="https://github.com/TalTech-IVAR-Lab/ros-desktop-docker" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VERSION}"

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/config \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    ROS_DISTRO=${ROS_DISTRO} \
    ROS_WS_NAME=ws_ivar_lab \
    ROS_WS_PATH=/config/ros/ws_ivar_lab

RUN . /etc/os-release && \
    pair="${ROS_DISTRO}:${VERSION_ID}" && \
    case "${pair}" in \
      humble:22.04|jazzy:24.04) ;; \
      *) echo "Unsupported ROS/Ubuntu pair: ${pair}" >&2; exit 64 ;; \
    esac

COPY files/ros.asc /usr/share/keyrings/ros-archive-keyring.asc

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      locales && \
    locale-gen en_US.UTF-8 && \
    . /etc/os-release && \
    printf 'deb [arch=%s signed-by=/usr/share/keyrings/ros-archive-keyring.asc] http://packages.ros.org/ros2/ubuntu %s main\n' \
      "$(dpkg --print-architecture)" "${VERSION_CODENAME}" \
      > /etc/apt/sources.list.d/ros2.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      python3-colcon-common-extensions \
      python3-rosdep \
      python3-vcstool \
      "ros-${ROS_DISTRO}-desktop" \
      "ros-${ROS_DISTRO}-moveit" && \
    if [ ! -e /etc/ros/rosdep/sources.list.d/20-default.list ]; then rosdep init; fi && \
    install -d -o "${DESKTOP_USER}" -g "${DESKTOP_USER}" -m 0755 /config/.ros && \
    runuser -u "${DESKTOP_USER}" -- env HOME=/config rosdep update && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY files/etc/ros-desktop/ /etc/ros-desktop/
COPY files/etc/s6-overlay/ /etc/s6-overlay/
COPY files/usr/local/libexec/ /usr/local/libexec/

RUN printf '. /etc/ros-desktop/root-home.sh\n' | cat - /etc/profile > /tmp/profile && \
    cat /tmp/profile > /etc/profile && \
    printf '. /etc/ros-desktop/root-home.sh\n' | cat - /etc/bash.bashrc > /tmp/bash.bashrc && \
    cat /tmp/bash.bashrc > /etc/bash.bashrc && \
    printf '. /etc/ros-desktop/root-home.sh\n' | cat - /etc/zsh/zshenv > /tmp/zshenv && \
    cat /tmp/zshenv > /etc/zsh/zshenv && \
    rm -f /tmp/profile /tmp/bash.bashrc /tmp/zshenv && \
    printf '\n# TalTech ROS desktop environment\nsource /etc/ros-desktop/setup.bash\n' \
      >> /etc/bash.bashrc && \
    printf '\n# TalTech ROS desktop environment\nsource /etc/ros-desktop/setup.zsh\n' \
      >> /etc/zsh/zshrc

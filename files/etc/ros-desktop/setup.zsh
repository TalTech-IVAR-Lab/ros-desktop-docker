# shellcheck shell=bash

case "${ROS_DISTRO:-}" in
    "noetic"|"humble"|"jazzy") ;;
    *) return 0 ;;
esac

source "/opt/ros/${ROS_DISTRO}/setup.zsh"

export ROS_WS_NAME="${ROS_WS_NAME:-workspace}"
export ROS_WS_PATH="${ROS_WS_PATH:-/home/${DESKTOP_USER:-ivar}/ros/${ROS_WS_NAME}}"

_taltech_desktop_uid=$(id -u "${DESKTOP_USER:-ivar}" 2>/dev/null || true)
if [[ -n ${_taltech_desktop_uid} && ${EUID} -eq ${_taltech_desktop_uid} ]]; then
    if [[ ${ROS_DISTRO:-} == "noetic" && -r "${ROS_WS_PATH}/devel/setup.zsh" ]]; then
        source "${ROS_WS_PATH}/devel/setup.zsh"
    elif [[ -r "${ROS_WS_PATH}/install/setup.zsh" ]]; then
        source "${ROS_WS_PATH}/install/setup.zsh"
    fi
fi
unset _taltech_desktop_uid

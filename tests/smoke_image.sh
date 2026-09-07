#!/usr/bin/env bash
set -Eeuo pipefail

image=${1:?usage: smoke_image.sh IMAGE ROS_DISTRO [PLATFORM]}
distro=${2:?usage: smoke_image.sh IMAGE ROS_DISTRO [PLATFORM]}
platform=${3:-linux/amd64}
desktop_user=${DESKTOP_USER:-ivar}
suffix="${distro}-${RANDOM}-${RANDOM}"
container="ros-smoke-${suffix}"
config_volume="ros-smoke-config-${suffix}"
state_volume="ros-smoke-state-${suffix}"
web_user=ci
web_password=ci-smoke-password

case "${distro}" in
    noetic|humble|jazzy) ;;
    *) printf 'unsupported ROS distro: %s\n' "${distro}" >&2; exit 64 ;;
esac
case "${platform}" in
    linux/amd64|linux/arm64) ;;
    *) printf 'unsupported platform: %s\n' "${platform}" >&2; exit 64 ;;
esac

show_logs() {
    docker logs "${container}" >&2 || true
}

cleanup() {
    docker rm -f "${container}" >/dev/null 2>&1 || true
    docker volume rm -f "${config_volume}" "${state_volume}" >/dev/null 2>&1 || true
}

trap show_logs ERR
trap cleanup EXIT

wait_for_runtime() {
    local attempt unauthenticated authenticated
    for attempt in $(seq 1 120); do
        if [[ $(docker inspect --format '{{.State.Running}}' "${container}" 2>/dev/null || true) != true ]]; then
            printf 'container stopped during startup\n' >&2
            return 1
        fi
        if docker exec "${container}" test -d /config/ros/ws_ivar_lab/src 2>/dev/null; then
            unauthenticated=$(docker exec "${container}" curl --insecure --silent \
                --output /dev/null --write-out '%{http_code}' \
                https://127.0.0.1:3001/ 2>/dev/null || true)
            authenticated=$(docker exec "${container}" curl --insecure --silent \
                --user "${web_user}:${web_password}" \
                --output /dev/null --write-out '%{http_code}' \
                https://127.0.0.1:3001/ 2>/dev/null || true)
            if [[ ${unauthenticated} == 401 && ${authenticated} == 200 ]]; then
                return 0
            fi
        fi
        sleep 2
    done
    printf 'runtime did not become ready with authenticated Selkies access\n' >&2
    return 1
}

start_container() {
    docker run --detach \
        --name "${container}" \
        --platform "${platform}" \
        --shm-size 1g \
        --env "CUSTOM_USER=${web_user}" \
        --env "PASSWORD=${web_password}" \
        --mount "source=${config_volume},target=/config" \
        --mount "source=${state_volume},target=/var/lib/taltech-desktop" \
        "${image}" >/dev/null
}

run_as_user() {
    docker exec -u "${desktop_user}" "${container}" bash -lc "$1"
}

check_ros_environment() {
    run_as_user \
        "source /opt/ros/${distro}/setup.bash; \
         test \"\${ROS_DISTRO}\" = '${distro}'; \
         rosdep db >/dev/null"
    if [[ ${distro} == noetic ]]; then
        run_as_user \
            'source /opt/ros/noetic/setup.bash; rospack find moveit_ros_move_group >/dev/null'
    else
        run_as_user \
            "source /opt/ros/${distro}/setup.bash; ros2 pkg prefix moveit_ros_move_group >/dev/null"
    fi
}

check_ros_communication() {
    if [[ ${distro} == noetic ]]; then
        docker exec --detach -u "${desktop_user}" "${container}" bash -lc \
            'source /opt/ros/noetic/setup.bash; exec roscore >/tmp/roscore.log 2>&1'
        for _ in $(seq 1 30); do
            if run_as_user \
                'source /opt/ros/noetic/setup.bash; rosparam list >/dev/null 2>&1'; then
                break
            fi
            sleep 1
        done
        run_as_user \
            'source /opt/ros/noetic/setup.bash; rosparam list >/dev/null'
        docker exec --detach -u "${desktop_user}" "${container}" bash -lc \
            'source /opt/ros/noetic/setup.bash; exec rostopic pub -r 5 /ci_chatter std_msgs/String "data: hello-noetic" >/tmp/ros-publisher.log 2>&1'
        run_as_user \
            'source /opt/ros/noetic/setup.bash; timeout 30 rostopic echo -n 1 /ci_chatter | grep -F hello-noetic'
    else
        docker exec --detach -u "${desktop_user}" "${container}" bash -lc \
            "source /opt/ros/${distro}/setup.bash; exec timeout 40 ros2 run demo_nodes_cpp talker \
              --ros-args -r chatter:=/ci_chatter >/tmp/ros2-talker.log 2>&1"
        run_as_user \
            "source /opt/ros/${distro}/setup.bash; timeout 35 ros2 topic echo --once \
              /ci_chatter std_msgs/msg/String | grep -F 'Hello World'"
    fi
}

check_rviz_stability() {
    local command status
    if [[ ${distro} == noetic ]]; then
        command='source /opt/ros/noetic/setup.bash; timeout 20 rviz >/tmp/rviz-smoke.log 2>&1'
    else
        command="source /opt/ros/${distro}/setup.bash; timeout 20 rviz2 >/tmp/rviz-smoke.log 2>&1"
    fi

    set +e
    run_as_user "${command}"
    status=$?
    set -e
    if [[ ${status} -ne 124 ]]; then
        docker exec "${container}" sh -c 'cat /tmp/rviz-smoke.log' >&2 || true
        printf 'RViz exited before the bounded smoke interval (status %s)\n' "${status}" >&2
        return 1
    fi
}

docker volume create "${config_volume}" >/dev/null
docker volume create "${state_volume}" >/dev/null

printf 'ROS_SMOKE_ROUND=initial distro=%s platform=%s\n' "${distro}" "${platform}"
start_container
wait_for_runtime
check_ros_environment

# The descriptor-rooted helper runs as the desktop user and must fail closed on
# a hostile symlink without touching its target.
run_as_user '
    set -e
    root=$(mktemp -d)
    mkdir "${root}/config" "${root}/protected"
    ln -s "${root}/protected" "${root}/config/ros"
    if /usr/local/libexec/taltech-init-ros-workspace.py \
        --config-root "${root}/config" --user "${DESKTOP_USER}"; then
        echo "workspace helper followed a symlink" >&2
        exit 1
    fi
    test -z "$(find "${root}/protected" -mindepth 1 -print -quit)"
    rm -rf "${root}"
'

if [[ ${distro} == noetic ]]; then
    overlay=devel
else
    overlay=install
fi

run_as_user \
    "mkdir -p /config/ros/ws_ivar_lab/${overlay}; \
     printf '%s\\n' 'export ROS_OVERLAY_SENTINEL=loaded' \
       > /config/ros/ws_ivar_lab/${overlay}/setup.bash; \
     printf '%s\\n' 'export ROS_OVERLAY_SENTINEL=loaded' \
       > /config/ros/ws_ivar_lab/${overlay}/setup.zsh; \
     printf '%s\\n' 'export ROS_DOTFILE_SENTINEL=loaded' > /config/.bashrc; \
     printf '%s\\n' 'export ROS_DOTFILE_SENTINEL=loaded' > /config/.bash_profile; \
     printf '%s\\n' 'export ROS_DOTFILE_SENTINEL=loaded' > /config/.zshenv; \
     printf '%s\\n' 'export ROS_DOTFILE_SENTINEL=loaded' > /config/.zshrc"

# Immutable ROS setup remains global. Root shells reset HOME before consulting
# writable /config dotfiles and never source a writable workspace overlay.
docker exec "${container}" bash -ic \
    'test "${HOME}" = /root && test "${ROS_DISTRO}" = "'"${distro}"'" && test "${ROS_OVERLAY_SENTINEL-unset}" = unset && test "${ROS_DOTFILE_SENTINEL-unset}" = unset'
docker exec "${container}" bash -lic \
    'test "${HOME}" = /root && test "${ROS_DOTFILE_SENTINEL-unset}" = unset'
docker exec "${container}" zsh -ic \
    'test "${HOME}" = /root && test "${ROS_DISTRO}" = "'"${distro}"'" && test "${ROS_OVERLAY_SENTINEL-unset}" = unset && test "${ROS_DOTFILE_SENTINEL-unset}" = unset'
docker exec -u "${desktop_user}" "${container}" bash -ic \
    'test "${ROS_OVERLAY_SENTINEL}" = loaded && test "${ROS_DOTFILE_SENTINEL}" = loaded'
docker exec -u "${desktop_user}" "${container}" zsh -ic \
    'test "${ROS_OVERLAY_SENTINEL}" = loaded && test "${ROS_DOTFILE_SENTINEL}" = loaded'

check_ros_communication
check_rviz_stability

state_identity=$(docker exec "${container}" sha256sum \
    /var/lib/taltech-desktop/ssh/ssh_host_ed25519_key.pub | cut -d ' ' -f 1)
if [[ ! ${state_identity} =~ ^[0-9a-f]{64}$ ]]; then
    printf 'invalid initial SSH host identity: %s\n' "${state_identity}" >&2
    exit 1
fi
run_as_user \
    "printf '%s\\n' '${distro}' > /config/ros/ws_ivar_lab/.ci-persistence"
docker rm -f "${container}" >/dev/null

printf 'ROS_SMOKE_ROUND=recreated distro=%s platform=%s\n' "${distro}" "${platform}"
start_container
wait_for_runtime
check_ros_environment
test "$(docker exec "${container}" cat /config/ros/ws_ivar_lab/.ci-persistence)" = "${distro}"
test "$(docker exec "${container}" sha256sum \
    /var/lib/taltech-desktop/ssh/ssh_host_ed25519_key.pub | cut -d ' ' -f 1)" = "${state_identity}"
check_ros_communication

printf 'ROS_SMOKE_TEST=PASS distro=%s platform=%s image=%s\n' \
    "${distro}" "${platform}" "${image}"

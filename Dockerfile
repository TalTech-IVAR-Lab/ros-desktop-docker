FROM taltechivarlab/ubuntu-desktop:20.04

# Set up sources
RUN sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list'

# Set up keys
RUN curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -

# Update indexes
RUN apt update -y

# Install desktop version of ROS Noetic
RUN apt install -y ros-noetic-desktop-full

# Install package building dependencies
RUN apt install -y \
  build-essential \
  python3-rosinstall \
  python3-rosinstall-generator \
  python3-wstool \
  python3-catkin-tools \
  python3-osrf-pycommon

# Install and initialize rosdep
RUN apt install -y python3-rosdep
RUN rosdep init
RUN rosdep update

# Define ROS version
ENV ROS_DISTRO="noetic"

# Install MoveIt and ROS-Industrial Core
RUN apt install -y ros-${ROS_DISTRO}-moveit ros-${ROS_DISTRO}-industrial-core

# Copy source files used to patch .zshrc and .bashrc
ENV HOME="/config"
ENV RC_FILE_PATCHES_PATH="${HOME}/rc_file_patches"
COPY files/rc_file_patches/ ${RC_FILE_PATCHES_PATH}

# Add command to source ROS to .zshrc
RUN cat ${RC_FILE_PATCHES_PATH}/source_ros.zsh >> ${HOME}/.zshrc
RUN cat ${RC_FILE_PATCHES_PATH}/source_ros.bash >> ${HOME}/.bashrc

# Create a default ROS workspace
ENV ROS_WS_NAME="ws_ivar_lab"
ENV ROS_WS_PATH="${HOME}/ros/${ROS_WS_NAME}"
RUN mkdir -p ${ROS_WS_PATH}
RUN wstool init ${ROS_WS_PATH}/src
WORKDIR ${ROS_WS_PATH}
RUN catkin config --extend /opt/ros/${ROS_DISTRO} --cmake-args -DCMAKE_BUILD_TYPE=Release
RUN catkin build

# Add command to source the default workspace to .zshrc and .bashrc
RUN cat ${RC_FILE_PATCHES_PATH}/source_default_ros_ws.zsh >> ${HOME}/.zshrc
RUN cat ${RC_FILE_PATCHES_PATH}/source_default_ros_ws.bash >> ${HOME}/.bashrc

# Clean up .*rc patch files
RUN rm -rf ${RC_FILE_PATCHES_PATH}

# Add ROS Noetic wallpaper and make it the default one
COPY files/ros_noetic_wallpaper.png /usr/share/backgrounds/ros/ros_noetic_wallpaper.png
RUN ln -snf /usr/share/backgrounds/ros/ros_noetic_wallpaper.png /usr/share/backgrounds/default.wallpaper

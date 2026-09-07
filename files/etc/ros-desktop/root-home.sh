# shellcheck shell=sh

# The desktop user's persistent home is inherited image-wide. Redirect
# privileged interactive shells before they resolve per-user startup files.
if [ "$(id -u)" -eq 0 ]; then
    export HOME=/root
fi

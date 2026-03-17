set -e
. /etc/os-release
ARCH=$(dpkg --print-architecture)
if [ "$NAME" = "Ubuntu" ]; then
    OS_URL="xUbuntu_${VERSION_ID}"
elif [ "$NAME" = "Debian GNU/Linux" ]; then
    OS_URL="Debian_${VERSION_ID}"
else
    OS_URL="xUbuntu_22.04"
fi
echo "OS_URL is $OS_URL"
echo "ARCH is $ARCH"
sudo apt-get update -y || true
DEB_NAME=$(curl -s "https://mega.nz/linux/repo/${OS_URL}/${ARCH}/" | grep -oP 'megacmd_[^"]*\.deb' | head -n 1)
echo "DEB_NAME is $DEB_NAME"
if [ -n "$DEB_NAME" ]; then
    wget -qO megacmd.deb "https://mega.nz/linux/repo/${OS_URL}/${ARCH}/${DEB_NAME}"
    echo "Running apt-get install"
    sudo apt-get install -y ./megacmd.deb || sudo apt-get install -f -y
    rm -f megacmd.deb
    echo "Done"
else
    echo "Failed to find megacmd package for ${OS_URL}/${ARCH}"
fi

if ! command -v google-chrome &> /dev/null; then
    echo "Installing Google Chrome..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
    apt-get update && apt-get install -y google-chrome-stable
fi

if ! command -v mega-get &> /dev/null; then
    echo "Installing MEGAcmd..."
    . /etc/os-release
    if [ "$NAME" = "Ubuntu" ]; then
        OS_URL="xUbuntu_${VERSION_ID}"
    elif [ "$NAME" = "Debian GNU/Linux" ]; then
        OS_URL="Debian_${VERSION_ID}"
    else
        OS_URL="xUbuntu_22.04"
    fi
    wget -q "https://mega.nz/linux/repo/${OS_URL}/amd64/megacmd-${OS_URL}_amd64.deb" -O megacmd.deb
    apt-get update && apt-get install -y ./megacmd.deb
    rm megacmd.deb
fi

python3 update.py && python3 -m bot

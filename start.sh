if ! command -v google-chrome &> /dev/null; then
    echo "Installing Google Chrome..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
    apt-get update && apt-get install -y google-chrome-stable
fi

if ! command -v mega-cmd &> /dev/null; then
    echo "Installing MEGAcmd..."
    wget -q https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb
    apt-get install -y ./megacmd-xUbuntu_22.04_amd64.deb || true
    rm ./megacmd-xUbuntu_22.04_amd64.deb
fi

python3 update.py && python3 -m bot

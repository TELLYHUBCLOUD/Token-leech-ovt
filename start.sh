if ! command -v megadl &> /dev/null; then
    echo "Installing megatools..."
    apt-get update && apt-get install -y megatools || true
fi

if ! command -v google-chrome &> /dev/null; then
    echo "Installing Google Chrome..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
    apt-get update && apt-get install -y google-chrome-stable
fi

pip3 uninstall -y mega mega.py
rm -rf /usr/local/lib/python*/dist-packages/mega*
python3 update.py && python3 -m bot

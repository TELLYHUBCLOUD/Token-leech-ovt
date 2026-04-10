FROM mysterysd/wzmlx:v3

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable

COPY requirements.txt .
RUN pip install --upgrade setuptools
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 uninstall -y mega mega.py || true
RUN rm -rf /usr/local/lib/python*/dist-packages/mega* || true
RUN pip3 install mega.py --no-cache-dir
RUN pip3 install --upgrade tenacity --no-deps

COPY . .

CMD ["bash", "start.sh"]

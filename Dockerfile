FROM silentdemonsd/wzmlx:hk

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update && apt-get install -y google-chrome-stable

RUN wget -q "https://mega.nz/linux/repo/xUbuntu_22.04/amd64/megacmd-xUbuntu_22.04_amd64.deb" -O megacmd.deb \
    && apt-get update && apt-get install -y ./megacmd.deb || apt-get install -f -y \
    && rm megacmd.deb

COPY requirements.txt .
RUN pip install --upgrade setuptools
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "start.sh"]

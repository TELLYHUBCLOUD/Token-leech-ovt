from os import path as ospath, listdir, makedirs
from time import time, sleep
import requests

from bot import LOGGER, task_dict
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.status_utils import (
    get_readable_file_size,
    MirrorStatus,
    get_readable_time,
)


class SeleniumDownloadStatus:
    def __init__(self, name, size, gid, listener):
        self._name = name
        self._size = size
        self._gid = gid
        self._listener = listener
        self.listener = listener
        self._downloaded = 0
        self._speed = 0
        self.message = listener.message
        self.is_waiting = False

    def set_progress(self, downloaded, speed):
        self._downloaded = downloaded
        self._speed = speed

    def gid(self):
        return self._gid

    def name(self):
        return self._name

    def size(self):
        return get_readable_file_size(self._size)

    def status(self):
        return MirrorStatus.STATUS_DOWNLOADING

    def downloaded(self):
        return get_readable_file_size(self._downloaded)

    def speed(self):
        return f"{get_readable_file_size(self._speed)}/s"

    def progress(self):
        if self._size == 0:
            return "0%"
        return f"{round(self._downloaded * 100 / self._size, 2)}%"

    def eta(self):
        if self._speed == 0:
            return "~"
        return get_readable_time((self._size - self._downloaded) / self._speed)

    def download(self):
        return self

    def task(self):
        return self

    def processed_bytes(self):
        return get_readable_file_size(self._downloaded)

    def engine(self):
        return "Selenium"

    def elapsed(self):
        return "~"

    def timeout(self):
        return "N/A"


async def add_selenium_download(listener, path, url):
    await listener.onDownloadStart()

    def _download_sync():
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
        except ImportError:
            import subprocess
            subprocess.run(["pip3", "install", "selenium"], check=True)
            from selenium import webdriver
            from selenium.webdriver.common.by import By

        makedirs(path, exist_ok=True)

        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--single-process')
        options.add_argument('--disable-extensions')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; '
                             'Win64; x64) AppleWebKit/537.36 (KHTML, '
                             'like Gecko) Chrome/120.0.0.0 Safari/537.36')

        prefs = {
            "download.default_directory": path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False
        }
        options.add_experimental_option("prefs", prefs)

        driver = webdriver.Chrome(options=options)

        try:
            LOGGER.info(f"Selenium opening URL: {url}")
            driver.get(url)
            sleep(10)  # wait for redirects and Cloudflare

            resolutions = ['360p', '480p', '720p', '1080p']
            found_links = {}

            def extract_links():
                links = driver.find_elements(By.TAG_NAME, "a")
                for link in links:
                    text = link.text.lower()
                    href = link.get_attribute("href")
                    if href:
                        for res in resolutions:
                            valid = res in text and res not in found_links
                            if valid and "http" in href:
                                found_links[res] = href

            extract_links()

            if not found_links:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for i in range(len(iframes)):
                    try:
                        src = iframes[i].get_attribute('src')
                        is_tgt = "razorshell" in src or "multiquality" in src
                        if src and is_tgt:
                            downlead_url = src.replace("/embed/", "/downlead/")
                            driver.get(downlead_url)
                            sleep(10)
                            extract_links()
                            if found_links:
                                break
                    except Exception:
                        continue

            if not found_links:
                raise Exception("No video links found to download.")

            for res, download_url in found_links.items():
                LOGGER.info(f"Downloading {res} from {download_url}")

                # Fetch total size
                total_size = 0
                try:
                    session = requests.Session()
                    for cookie in driver.get_cookies():
                        session.cookies.set(cookie['name'], cookie['value'])
                    ua = driver.execute_script("return navigator.userAgent;")
                    session.headers.update({"User-Agent": ua})

                    res_head = session.head(
                        download_url, allow_redirects=True, timeout=10
                    )
                    if 'Content-Length' in res_head.headers:
                        total_size = int(res_head.headers['Content-Length'])
                except Exception:
                    pass

                initial_files = set(listdir(path))
                driver.get(download_url)

                st_name = f"Video_{res}.mp4"
                status = SeleniumDownloadStatus(
                    st_name, total_size, f"sel_{res}", listener
                )

                # Dictionary assignment is thread-safe in Python
                task_dict[listener.mid] = status

                downloading = True
                wait_time = 0
                last_size = 0
                last_time = time()

                while downloading:
                    sleep(1)
                    wait_time += 1

                    current_files = set(listdir(path))
                    crd = [f for f in current_files
                           if f.endswith('.crdownload')]

                    if crd:
                        filepath = ospath.join(path, crd[0])
                        if ospath.exists(filepath):
                            current_size = ospath.getsize(filepath)

                            now = time()
                            time_diff = now - last_time
                            size_diff = current_size - last_size
                            spd = size_diff / time_diff if time_diff > 0 else 0

                            status.set_progress(current_size, spd)
                            status._name = crd[0].replace('.crdownload', '')

                            last_size = current_size
                            last_time = now
                            wait_time = 0
                    else:
                        new_files = current_files - initial_files - set(crd)
                        if new_files:
                            LOGGER.info(f"Selenium finished downloading {res}")
                            downloading = False
                        else:
                            if wait_time > 30:
                                warning_msg = f"Timeout waiting for {res} " \
                                              f"to start downloading."
                                LOGGER.warning(warning_msg)
                                downloading = False

        except Exception as e:
            LOGGER.error(f"Selenium download thread error: {e}")
            raise e
        finally:
            driver.quit()

    try:
        await sync_to_async(_download_sync)
        await listener.onDownloadComplete()
    except Exception as e:
        await listener.onDownloadError(f"Selenium Error: {e}")

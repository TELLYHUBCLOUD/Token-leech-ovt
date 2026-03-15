from os import path as ospath, listdir, makedirs
from aiofiles.os import remove, path as aiopath
from time import time
from asyncio import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
import requests

from bot import LOGGER, bot_loop, task_dict, task_dict_lock
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.status_utils import get_readable_file_size, MirrorStatus, get_readable_time


class SeleniumDownloadStatus:
    def __init__(self, name, size, gid, listener):
        self._name = name
        self._size = size
        self._gid = gid
        self._listener = listener
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


async def add_selenium_download(listener, path, url):
    await listener.onDownloadStart()

    def _download_sync():
        makedirs(path, exist_ok=True)

        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

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
            sleep(5) # wait for redirects

            resolutions = ['360p', '480p', '720p', '1080p']
            found_links = {}

            def extract_links():
                links = driver.find_elements(By.TAG_NAME, "a")
                for link in links:
                    text = link.text.lower()
                    href = link.get_attribute("href")
                    if href:
                        for res in resolutions:
                            if res in text and res not in found_links and "http" in href:
                                found_links[res] = href

            extract_links()

            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for i in range(len(iframes)):
                try:
                    driver.switch_to.frame(i)
                    extract_links()
                    driver.switch_to.default_content()
                except Exception:
                    driver.switch_to.default_content()
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
                    user_agent = driver.execute_script("return navigator.userAgent;")
                    session.headers.update({"User-Agent": user_agent})

                    res_head = session.head(download_url, allow_redirects=True, timeout=10)
                    if 'Content-Length' in res_head.headers:
                        total_size = int(res_head.headers['Content-Length'])
                except:
                    pass

                initial_files = set(listdir(path))
                driver.get(download_url)

                status = SeleniumDownloadStatus(f"Video_{res}.mp4", total_size, f"sel_{res}", listener)
                with task_dict_lock:
                    task_dict[listener.mid] = status

                downloading = True
                wait_time = 0
                last_size = 0
                last_time = time()

                while downloading:
                    sleep(1)
                    wait_time += 1

                    current_files = set(listdir(path))
                    crdownloads = [f for f in current_files if f.endswith('.crdownload')]

                    if crdownloads:
                        filepath = ospath.join(path, crdownloads[0])
                        if ospath.exists(filepath):
                            current_size = ospath.getsize(filepath)

                            now = time()
                            time_diff = now - last_time
                            size_diff = current_size - last_size
                            speed_bps = size_diff / time_diff if time_diff > 0 else 0

                            status.set_progress(current_size, speed_bps)
                            status._name = crdownloads[0].replace('.crdownload', '')

                            last_size = current_size
                            last_time = now
                            wait_time = 0
                    else:
                        new_files = current_files - initial_files - set(crdownloads)
                        if new_files:
                            LOGGER.info(f"Selenium finished downloading {res}")
                            downloading = False
                        else:
                            if wait_time > 30:
                                LOGGER.warning(f"Timeout waiting for {res} to start downloading.")
                                downloading = False

        finally:
            driver.quit()

    try:
        await sync_to_async(_download_sync)
        await listener.onDownloadComplete()
    except Exception as e:
        await listener.onDownloadError(str(e))

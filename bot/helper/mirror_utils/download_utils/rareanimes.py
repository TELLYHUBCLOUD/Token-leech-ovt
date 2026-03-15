import time
import subprocess
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException

def rareanimes_bypass(url: str) -> dict:
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
    except ImportError:
        import subprocess
        subprocess.run(["pip3", "install", "selenium"], check=True)
        from selenium import webdriver
        from selenium.webdriver.common.by import By

    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--single-process')
    options.add_argument('--disable-extensions')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(10)

        resolutions = ['360p', '480p', '720p', '1080p']
        found_links = {}

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if not iframes:
            time.sleep(5)
            iframes = driver.find_elements(By.TAG_NAME, "iframe")

        for i in range(len(iframes)):
            src = iframes[i].get_attribute('src')
            if src and ("razorshell" in src or "multiquality" in src):
                downlead_url = src.replace("/embed/", "/downlead/")
                driver.get(downlead_url)
                time.sleep(5)
                links = driver.find_elements(By.TAG_NAME, "a")
                for link in links:
                    text = link.text.lower()
                    href = link.get_attribute("href")
                    if href:
                        for res in resolutions:
                            if res in text and res not in found_links and "http" in href:
                                found_links[res] = href
                break

        driver.quit()

        if not found_links:
            raise DirectDownloadLinkException("No download links found for this URL.")

        # Return format expected by bypass:
        # dict with 'contents': [{'url': 'link 360p (360p)'}, {'url': 'link 480p (480p)'}]
        contents = []
        for res, link in found_links.items():
            contents.append({'url': f"{link} ({res})"})

        return {'contents': contents}
    except Exception as e:
        if 'driver' in locals():
            driver.quit()
        raise DirectDownloadLinkException(f"ERROR: {e}")

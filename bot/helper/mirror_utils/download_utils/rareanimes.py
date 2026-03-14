import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException

def rareanimes_bypass(url: str) -> dict:
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')

    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(5)

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

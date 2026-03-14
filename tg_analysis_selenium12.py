from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

url = "https://codedew.com/zipper/?url=0lzI5U5IQaCNyAMeXIe7C%2FmxHvoUz6Go3uiZfPDfAWXFKy0lIeLFLT0alPoRBOsEHJrNHE%2Ft5yd588tNtanfTWuqoav51gAacQARzbyknuPeodU%3D"
options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.get(url)
time.sleep(5)

print("Check if iframe loads properly...")
iframe_srcs = [iframe.get_attribute("src") for iframe in driver.find_elements(By.TAG_NAME, "iframe")]
print("Total iframes:", len(iframe_srcs))

resolutions = ['360p', '480p', '720p', '1080p']
found_links = {}

def extract_links():
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        text = link.text.lower()
        href = link.get_attribute("href")
        print("A-Tag:", text, href)
        if href:
            for res in resolutions:
                if res in text and res not in found_links and "http" in href:
                    found_links[res] = href

print("Extracting main frame...")
extract_links()

for i in range(len(iframe_srcs)):
    try:
        driver.switch_to.frame(i)
        print("Switched to iframe", i)
        # Wait a bit inside the iframe to make sure content is loaded
        time.sleep(5)
        extract_links()
        driver.switch_to.default_content()
    except Exception as e:
        print("Iframe error:", e)
        driver.switch_to.default_content()
        continue

print("Found Links:", found_links)
driver.quit()

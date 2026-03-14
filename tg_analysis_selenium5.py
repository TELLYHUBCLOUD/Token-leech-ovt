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

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.get(url)
print("Waiting...")
time.sleep(10)
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
    except Exception as e:
        print("Iframe error:", e)
        driver.switch_to.default_content()
        continue

print("Found links:", found_links)
driver.quit()

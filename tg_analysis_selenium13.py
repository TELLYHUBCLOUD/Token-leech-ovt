from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

print("Wait for page to load...")
time.sleep(15)

resolutions = ['360p', '480p', '720p', '1080p']
found_links = {}

print("Checking main frame...")
for link in driver.find_elements(By.TAG_NAME, "a"):
    print("Main A-Tag:", link.text, link.get_attribute("href"))

iframes = driver.find_elements(By.TAG_NAME, "iframe")
print("Total iframes:", len(iframes))

for i in range(len(iframes)):
    try:
        driver.switch_to.frame(i)
        print(f"Switched to iframe {i}. Waiting for elements...")
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            text = link.text.lower()
            href = link.get_attribute("href")
            print("Iframe A-Tag:", text, href)
            if href:
                for res in resolutions:
                    if res in text and res not in found_links and "http" in href:
                        found_links[res] = href
        driver.switch_to.default_content()
    except Exception as e:
        print("Iframe error:", type(e).__name__)
        driver.switch_to.default_content()
        continue

print("Found Links:", found_links)
driver.quit()

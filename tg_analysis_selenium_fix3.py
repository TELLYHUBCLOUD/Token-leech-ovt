# Okay, so Cloudflare blocks requests to `downlead`! We need selenium to execute javascript.
# But wait, why did it fail on Heroku?
# Let's check `rareanimes.py`
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from selenium.webdriver.common.by import By

url = "https://codedew.com/zipper/?url=%2Btfompy7uC0qQ9QqldEBW3nuSU4YydKGvADqbgf6BMfoP4zYBim9WL3LfOBZzVb8xSVULp1w9rrsLI89UEg5x%2BeAPkAiFfI4ArQj71doES5DnDU%3D"
options = webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

driver.get(url)
print("Waiting 10s for initial load...")
time.sleep(10)

iframes = driver.find_elements(By.TAG_NAME, "iframe")
print("Found iframes:", len(iframes))

resolutions = ['360p', '480p', '720p', '1080p']
found_links = {}

for iframe in iframes:
    src = iframe.get_attribute('src')
    print("Iframe SRC:", src)
    if src and ("razorshell" in src or "multiquality" in src):
        downlead_url = src.replace("/embed/", "/downlead/")
        print("Navigating to:", downlead_url)
        driver.get(downlead_url)
        time.sleep(10)
        print("Current URL:", driver.current_url)
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            text = link.text.lower()
            href = link.get_attribute("href")
            print("Found link text:", text, "href:", href)
            if href:
                for res in resolutions:
                    if res in text and res not in found_links and "http" in href:
                        found_links[res] = href
        break
print("Final found:", found_links)
driver.quit()

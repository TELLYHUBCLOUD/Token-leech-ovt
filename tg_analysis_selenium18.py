from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

url = "https://swift.multiquality.click/downlead/K9nnRuS8NlGZgnw"
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
links = driver.find_elements(By.TAG_NAME, "a")
found_links = {}
resolutions = ['360p', '480p', '720p', '1080p']
for link in links:
    text = link.text.lower()
    href = link.get_attribute("href")
    if href:
        for res in resolutions:
            if res in text and res not in found_links and "http" in href:
                found_links[res] = href
print("Found links:", found_links)
driver.quit()

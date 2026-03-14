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
for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
    src = iframe.get_attribute("src")
    if "argon.razorshell.space" in src or "swift" in src:
        driver.get(src)
        time.sleep(5)
        # Check title
        print("Title:", driver.title)
        # Wait for potential cloudflare redirect
        time.sleep(10)
        print("Title after 10s:", driver.title)
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            print("Link:", link.text, link.get_attribute("href"))

driver.quit()

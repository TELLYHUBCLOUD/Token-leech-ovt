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
print("Current URL:", driver.current_url)

iframes = driver.find_elements(By.TAG_NAME, "iframe")
print("Number of iframes:", len(iframes))
for i in range(len(iframes)):
    src = iframes[i].get_attribute('src')
    print("Iframe SRC:", src)
    if "razorshell.space" in src or "swift.multiquality.click" in src:
        driver.get(src)
        time.sleep(5)
        print("Navigated to iframe src directly:", driver.current_url)
        break
else:
    print(driver.page_source[:500])

links = driver.find_elements(By.TAG_NAME, "a")
for link in links:
    print(link.text, link.get_attribute("href"))

driver.quit()

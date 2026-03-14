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

iframes = driver.find_elements(By.TAG_NAME, "iframe")
print("Total iframes:", len(iframes))
iframe_srcs = [i.get_attribute('src') for i in iframes]

for src in iframe_srcs:
    if src and ("razorshell" in src or "swift" in src):
        print("Switching to iframe...")
        driver.get(url) # Reset
        time.sleep(2)
        iframe = driver.find_element(By.XPATH, f"//iframe[@src='{src}']")
        driver.switch_to.frame(iframe)
        time.sleep(5)
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            print("Link inside frame:", link.text, link.get_attribute("href"))

driver.quit()

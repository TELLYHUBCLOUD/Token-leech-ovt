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

print("Navigating to URL...")
driver.get(url)
time.sleep(8)
print("Finding links...")
links = driver.find_elements(By.TAG_NAME, "a")
for link in links:
    print("Link:", link.text, link.get_attribute("href"))

print("Finding iframes...")
iframes = driver.find_elements(By.TAG_NAME, "iframe")
print("Total iframes:", len(iframes))

for index in range(len(iframes)):
    driver.switch_to.frame(index)
    print(f"Inside iframe {index}:")
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        print("Link:", link.text, link.get_attribute("href"))
    driver.switch_to.default_content()

driver.quit()

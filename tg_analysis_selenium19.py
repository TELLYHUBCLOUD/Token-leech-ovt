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
links = driver.find_elements(By.TAG_NAME, "a")
print("Main window links:")
for link in links:
    print(link.get_attribute("href"))

found_links = {}
resolutions = ['360p', '480p', '720p', '1080p']

# The original script does:
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
        print(f"Inside iframe {i}")
        extract_links()

        # What if we need to get the download links from the `downlead` URL directly?
        # The user script originally used `swift.multiquality.click/downlead/...`
        # Here we are at `codedew.com`, which has an iframe to `argon.razorshell.space/embed/...`
        # Does the iframe contain `downlead` links?
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and "downlead" in href:
                print("Found downlead href!", href)
                # Maybe we can navigate to this href to get the actual download links?

        driver.switch_to.default_content()
    except Exception as e:
        driver.switch_to.default_content()

print("Found links:", found_links)
driver.quit()

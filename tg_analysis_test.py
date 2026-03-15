from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time

url = "https://codedew.com/zipper/?url=0lzI5U5IQaCNyAMeXIe7C%2FmxHvoUz6Go3uiZfPDfAWXFKy0lIeLFLT0alPoRBOsEHJrNHE%2Ft5yd588tNtanfTWuqoav51gAacQARzbyknuPeodU%3D"
# Wait, this URL might not give any links? The user screenshot said "No download links found for this URL."
# Ah, the user said "Ye jo https://rareanimes.app ka banaya tha Mane bo eske leye banaya tha Thik hai"
# Meaning they want codedew.com to work, but the previous test returned NO LINKS for the user's specific URL!

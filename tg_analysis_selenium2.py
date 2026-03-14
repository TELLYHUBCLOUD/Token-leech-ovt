import requests
from bs4 import BeautifulSoup

url = "https://codedew.com/zipper/?url=0lzI5U5IQaCNyAMeXIe7C%2FmxHvoUz6Go3uiZfPDfAWXFKy0lIeLFLT0alPoRBOsEHJrNHE%2Ft5yd588tNtanfTWuqoav51gAacQARzbyknuPeodU%3D"
res = requests.get(url, allow_redirects=True)
soup = BeautifulSoup(res.text, "html.parser")
print(soup.prettify()[:1000])

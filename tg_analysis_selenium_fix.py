import requests
from bs4 import BeautifulSoup
import time

# Let's inspect the exact URL the user provided
url = "https://codedew.com/zipper/?url=%2Btfompy7uC0qQ9QqldEBW3nuSU4YydKGvADqbgf6BMfoP4zYBim9WL3LfOBZzVb8xSVULp1w9rrsLI89UEg5x%2BeAPkAiFfI4ArQj71doES5DnDU%3D"
res = requests.get(url, allow_redirects=True)
print("Initial request to codedew.com/zipper/")
print("Status:", res.status_code)
print("Final URL:", res.url)

soup = BeautifulSoup(res.text, 'html.parser')
for i, iframe in enumerate(soup.find_all('iframe')):
    print(f"Iframe {i}: {iframe.get('src')}")

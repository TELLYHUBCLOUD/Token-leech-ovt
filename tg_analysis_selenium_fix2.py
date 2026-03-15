import requests
from bs4 import BeautifulSoup

# Can we just use requests instead of selenium?
# The user's selenium script waits 5s. But if we can just scrape the downlead url directly from the iframe src?
url = "https://codedew.com/zipper/?url=%2Btfompy7uC0qQ9QqldEBW3nuSU4YydKGvADqbgf6BMfoP4zYBim9WL3LfOBZzVb8xSVULp1w9rrsLI89UEg5x%2BeAPkAiFfI4ArQj71doES5DnDU%3D"
res = requests.get(url, allow_redirects=True)
soup = BeautifulSoup(res.text, 'html.parser')
for iframe in soup.find_all('iframe'):
    src = iframe.get('src')
    if src and ('razorshell' in src or 'multiquality' in src):
        downlead_url = src.replace("/embed/", "/downlead/")
        print("Derived downlead:", downlead_url)

        # Now fetch the downlead URL with requests
        res2 = requests.get(downlead_url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        print("Downlead Status:", res2.status_code)

        soup2 = BeautifulSoup(res2.text, 'html.parser')
        for a in soup2.find_all('a'):
            href = a.get('href')
            text = a.text.lower()
            if href:
                print("Link:", text, href)

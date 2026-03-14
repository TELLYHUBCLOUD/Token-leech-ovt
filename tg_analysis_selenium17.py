import requests

dl_url = "https://argon.razorshell.space/downlead/K9nnRuS8NlGZgnw"
res = requests.get(dl_url, allow_redirects=True)
print("Status:", res.status_code)
print("URL:", res.url)

dl_url2 = "https://swift.multiquality.click/downlead/K9nnRuS8NlGZgnw"
res2 = requests.get(dl_url2, allow_redirects=True)
print("Status2:", res2.status_code)
print("URL2:", res2.url)

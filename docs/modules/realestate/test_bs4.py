import requests
from bs4 import BeautifulSoup

# url = "https://www.loopnet.com/for-lease/retail/"
# url = "https://www.loopnet.com/search/commercial-real-estate/usa/auctions/"
url = "https://www.loopnet.com/search/commercial-real-estate/usa/auctions/?sk=cb57058f50bc941af82bafe911a3ed0f"


r_headers = requests.utils.default_headers()

# {
#     'User-Agent': 'python-requests/2.31.0',
#     'Accept-Encoding': 'gzip, deflate',
#     'Accept': '*/*',
#     'Connection': 'keep-alive',
# }

# headers = {
#     "User-Agent": "Mozilla/5.0"
# }


response = requests.get(url, headers=r_headers)
soup = BeautifulSoup(response.text, "html.parser")

for listing in soup.select(".placardTitle"):
    print(listing.get_text(strip=True))

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from parsel import Selector
import time
from fake_headers import Headers

# Setup Chrome options
options = uc.ChromeOptions()
options.add_argument("--headless=new")  # Use new headless mode
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")  # Add no sandbox for Windows
options.add_argument("--disable-dev-shm-usage")  # Disable /dev/shm usage

headers = Headers(headers=True).generate()

# Start undetected Chrome browser
try:
    driver = uc.Chrome(options=options)
    
    # Go to the LoopNet auctions page
    driver.get("https://www.loopnet.com/search/commercial-real-estate/usa/auctions/")
    time.sleep(5)  # Wait for page to load

    # Get page source and parse
    sel = Selector(text=driver.page_source)

    # Example: Extract property titles and links
    for listing in sel.css("div.card--property"):
        title = listing.css("a.card-title::text").get()
        link = listing.css("a.card-title::attr(href)").get()
        print(f"Title: {title} | Link: {link}")

    driver.quit()
except Exception as e:
    print(f"Error: {e}")

from selenium import webdriver
import csv
import os
import time
from parsel import Selector
import requests
from fake_headers import Headers
import datetime
import platform
import json


def getstart(url, county, page):
    driver.get(url + '/' + str(page))
    time.sleep(5)
    try:
        jsondata = json.loads(Selector(text=driver.page_source).xpath('.//*[@type="application/ld+json"]/text()[contains(.,"SearchResultsPage")]').extract_first())
        links = [i['item']['url'] for i in jsondata['about']]
    except:
        links = []
    
    if not links:
        try:
            jsondata = json.loads(Selector(text=driver.page_source).xpath('.//*[@type="application/ld+json"]/text()[contains(.,"SearchResultsPage")]').extract_first())
            links = [jsondata['about']['url']]
        except:
            links = []

    print(len(links))
    for link in links:
        if link not in alreadyscrapped:
            alreadyscrapped.append(link)
            date_time = datetime.datetime.now().strftime('%y-%m-%d')
            response = Selector(text=requests.get(link, headers=Headers().generate()).text)
            time.sleep(2)
            # Extract details
            try:
                title = ', '.join(Selector(text=response.xpath('.//*[@class="profile-hero-heading"]/h1').extract_first()).xpath('.//span/text()').extract())
            except:
                title = ''
            try:
                location = ' '.join(response.xpath('.//*[@id="breadcrumb-section"]/h1/text()').extract())
            except:
                location = ''
            price = response.xpath('.//td[contains(.,"Price")]/following-sibling::td/span/text()').extract_first()
            apartment_style = response.xpath('.//td[contains(.,"Apartment Style")]/following-sibling::td/span/text()').extract_first()
            price_per_unit = response.xpath('.//td[contains(.,"Price Per Unit")]/following-sibling::td/span/text()').extract_first()
            building_class = response.xpath('.//td[contains(.,"Building Class")]/following-sibling::td/span/text()').extract_first()
            sale_type = response.xpath('.//td[contains(.,"Sale Type")]/following-sibling::td/span/text()').extract_first()
            lot_size = response.xpath('.//td[contains(.,"Lot Size")]/following-sibling::td/span/text()').extract_first()
            cap_rate = response.xpath('.//td[contains(.,"Cap Rate")]/following-sibling::td/span/text()').extract_first()
            building_size = response.xpath('.//td[contains(.,"Building Size")]/following-sibling::td/span/text()').extract_first()
            sale_conditions = response.xpath('.//td[contains(.,"Sale Conditions")]/following-sibling::td/span/text()').extract_first()
            average_occupancy = response.xpath('.//td[contains(.,"Average Occupancy")]/following-sibling::td/span/text()').extract_first()
            no_units = response.xpath('.//td[contains(.,"No. Units")]/following-sibling::td/span/text()').extract_first()
            no_stores = response.xpath('.//td[contains(.,"No. Stories")]/following-sibling::td/span/text()').extract_first()
            property_type = response.xpath('.//td[contains(.,"Property Type")]/following-sibling::td/span/text()').extract_first()
            year_build = response.xpath('.//td[contains(.,"Year Built/Renovated")]/following-sibling::td/span/text()').extract_first()
            property_subtype = response.xpath('.//td[contains(.,"Property Subtype")]/following-sibling::td/span/text()').extract_first()

            # Save data to CSV
            with open("loopnet.csv", "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([date_time, county, link, title, location, price, apartment_style, price_per_unit, building_class, sale_type, lot_size, cap_rate, building_size, sale_conditions,
                                 average_occupancy, no_units, no_stores, property_type, year_build, property_subtype])
                print([date_time, county, link, title, location, price, apartment_style, price_per_unit, building_class, sale_type, lot_size, cap_rate, building_size, sale_conditions,
                       average_occupancy, no_units, no_stores, property_type, year_build, property_subtype])
        else:
            print("Exists ...")

    if links:
        getstart(url, county, page + 1)
        


if __name__ == '__main__':
    if "loopnet.csv" not in os.listdir(os.getcwd()):
        with open("loopnet.csv", "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'county', 'link', 'title', 'location', 'price', 'apartment_style', 'price_per_unit', 'building_class', 'sale_type', 'lot_size', 'cap_rate', 'building_size',
                             'sale_conditions', 'average_occupancy', 'no_units', 'no_stores', 'property_type', 'year_build', 'property_subtype'])

    alreadyscrapped = []
    with open("loopnet.csv", "r") as r:
        reader = csv.reader(r)
        for line in reader:
            alreadyscrapped.append(line[2])

    if platform.system() == "Linux":
        driver = webdriver.Firefox()
    else:
        driver = webdriver.Firefox(executable_path=os.getcwd() + '/geckodriver')

    urls = {
        'https://www.loopnet.com/search/apartment-buildings/los-angeles-county-ca/for-sale/': 'Los Angeles',
        'https://www.loopnet.com/search/apartment-buildings/fresno-county-ca/for-sale/': 'Fresno',
        'https://www.loopnet.com/search/apartment-buildings/kings-county-ca/for-sale': 'Kings',
        'https://www.loopnet.com/search/apartment-buildings/tulare-county-ca/for-sale': 'Tulare',
        'https://www.loopnet.com/search/apartment-buildings/madera-county-ca/for-sale/': 'Madera',
        'https://www.loopnet.com/search/apartment-buildings/monterey-county-ca/for-sale': 'Monterey',
        'https://www.loopnet.com/search/apartment-buildings/san-benito-county-ca/for-sale': 'San-Benito',
        'https://www.loopnet.com/search/apartment-buildings/kern-county-ca/for-sale': 'Kern',
        'https://www.loopnet.com/search/apartment-buildings/merced-county-ca/for-sale': 'Merced',
        'https://www.loopnet.com/search/apartment-buildings/sutter-county-ca/for-sale': 'Sutter',
        'https://www.loopnet.com/search/apartment-buildings/sacramento-county-ca/for-sale': 'Sacramento',
        'https://www.loopnet.com/search/apartment-buildings/el-dorado-county-ca/for-sale': 'El Dorado',
        'https://www.loopnet.com/search/apartment-buildings/amador-county-ca/for-sale': 'Amador',
        'https://www.loopnet.com/search/apartment-buildings/san-joaquin-county-ca/for-sale': 'San-Joaquin',
        'https://www.loopnet.com/search/apartment-buildings/solano-county-ca/for-sale': 'Solano',
        'https://www.loopnet.com/search/apartment-buildings/contra-costa-county-ca/for-sale': 'Contra-Costa',
        'https://www.loopnet.com/search/apartment-buildings/yolo-county-ca/for-sale': 'Yolo',
        'https://www.loopnet.com/search/apartment-buildings/placer-county-ca/for-sale': 'Placer',
        'https://www.loopnet.com/search/apartment-buildings/san-diego-county-ca/for-sale': 'San-Diego',
        'https://www.loopnet.com/search/apartment-buildings/orange-county-ca/for-sale': 'Orange',
        'https://www.loopnet.com/search/apartment-buildings/riverside-county-ca/for-sale': 'Riverside',
        'https://www.loopnet.com/search/apartment-buildings/imperial-county-ca/for-sale': 'Imperial'
    }

    for k, v in urls.items():
        getstart(k, v, 1)

    driver.close()
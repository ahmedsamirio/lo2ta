import re, requests, bs4, logging, threading, time, random
import pandas as pd
import numpy as np


from .config import *
from datetime import datetime
from django.core.management.base import BaseCommand
from curator.models import Ad, Brand, Model


def get_full_ad_info(link_soup):
    """ Returns the full ad infomation in a readable format """
    full_raw_info = link_soup.select('.details strong a')  # full ad information in soupified html format
    full_processed_info = []
    for info in full_raw_info:
        processed_info = re.sub('\t|\n', '', info.get_text())
        full_processed_info.append(processed_info)
    return full_processed_info

def get_full_ad_info_ids(link_soup):
    """ Returns the ad information identifiers (headers) """
    raw_ids = link_soup.select('.details th')  # identifiers in soupified html format
    processed_ids = [id.get_text() for id in raw_ids]
    return processed_ids

def get_info_from_id(id, full_info, full_info_ids):
    """ Return a single ad info by specifing it's id counterpart """
    if id in full_info_ids:
        info_idx = full_info_ids.index(id)  # get the id index to return its info counterpart
        return full_info[info_idx].strip()  # normalize text by stipping excess whitepsace

def get_car_features(full_info, full_info_ids):
    """ Returns a list containig all car features mentioned in the ad """
    # find the features id index to remove things before it
    cut_off = len(full_info_ids) - full_info_ids.index('إضافات') - 1
    car_features = full_info[7:-cut_off]  # the slice of the full info containing the ads

    # since all car features are accounted for with only one id, we need to remove
    # these features and their counterpart id in order to be able to extract 
    # the remaining ad info by using the index counterpart way used in get_info_from_id
    for feature in car_features:
        full_info.remove(feature)
    full_info_ids.remove('إضافات')
    return car_features


def process_arabic_date(date):
    month_dict = {"يناير": "1",
                  "فبراير": "2",
                  "مارس": "3",
                  "أبريل": "4",
                  "مايو": "5",
                  "يونيو": "6",
                  "يوليو": "7",
                  "أغسطس": "8",
                  "سبتمبر": "9",
                  "أكتوبر": "10",
                  "نوفمبر": "11",
                  "ديسمبر": "12",}
    date =  "-".join([month_dict.get(x, x) for x in date.split()])
    return datetime.strptime(date, '%d-%m-%Y')


def get_date(link_soup):
    try:
        date = re.sub('\t|\n', '', link_soup.select('p small span')[0].get_text()).split(',')[1]
        return datetime.date(process_arabic_date(date))
    except:
        return 0

def get_ad_location(link_soup):
    try:
        location = link_soup.select(".show-map-link strong")[0].get_text().strip().split("،")
        if len(location) != 2:
            location = link_soup.select(".show-map-link strong")[0].get_text().strip().split(",")
        return location
    except:
        logging.critical('Error in get_ad_lcation')
        logging.critical(link_soup.select(".show-map-link strong"))
        return None, None

def get_price(link_soup, link):
    try:
        price = link_soup.select('div .pricelabel strong')[0].get_text()
        price = re.search('\d*,\d*', price).group().replace(',','')
    except:
        try:
            price = link_soup.select('div .pricelabel strong')[0].get_text()
            price = re.search('\d*', price).group().replace(',','') 
        except:
            logging.critical('Error in get_price.')
            logging.critical(link_soup.select('div .pricelabel strong'))
            logging.critical(link['href'])
            return 0
    return price

def get_brand(link_soup, city): 
    try:
        brand = link_soup.select('td.middle span')[-1].get_text().replace(city, '') 
        return brand.strip()  # normalize text by stripping excess whitepsace
    except:
        logging.critical('Error in get_brand.')
        return 0


def get_imgs(link_soup):
    imgs = []
    for div in link_soup.findAll("div", {"class": "photo-glow"}):
        img = div.find('img').get('src')
        imgs.append(img)
    return imgs


def get_text_description(link_soup):
    description = link_soup.select("#textContent p")[0].get_text().strip()
    return description


def make_ad_dict(link_soup, link):
    """ Returns a dictionary with all the relevant ad info """
    
    ad_dict = dict.fromkeys(['Brand', 'Model', 'Governerate', 'City', 'Date', 'Year', 'Kilometers', 'Pay_type',
                         'Ad_type','Transmission', 'CC', 'Chasis', 'Features', 'Color', 'Price', 'URL', 'imgs', 
                         'Description'])

    ad_dict['Date'] = get_date(link_soup)
    ad_dict['Price'] = get_price(link_soup, link)
    ad_dict['imgs'] = get_imgs(link_soup)
    ad_dict['City'], ad_dict['Governerate'] = get_ad_location(link_soup) 
    ad_dict['Brand'] = get_brand(link_soup, ad_dict['City'])
    ad_dict['Description'] = get_text_description(link_soup)
    ad_dict['URL'] = link['href']

    ad_info = get_full_ad_info(link_soup)
    ad_info_ids = get_full_ad_info_ids(link_soup)

    ad_dict['CC'] = get_info_from_id('المحرك (سي سي)', ad_info, ad_info_ids) 
    ad_dict['Year'] = get_info_from_id('السنة', ad_info, ad_info_ids) 
    ad_dict['Model'] = get_info_from_id('موديل', ad_info, ad_info_ids) 
    ad_dict['State'] = get_info_from_id('الحالة', ad_info, ad_info_ids) 
    ad_dict['Pay_type'] = get_info_from_id('طريقة الدفع', ad_info, ad_info_ids) 
    ad_dict['Kilometers'] = get_info_from_id('كيلومترات', ad_info, ad_info_ids) 
    ad_dict['Transmission'] = get_info_from_id('ناقل الحركة', ad_info, ad_info_ids) 

    if 'إضافات' in ad_info_ids:
        ad_dict['Features'] = get_car_features(ad_info, ad_info_ids)

    ad_dict['Color'] = get_info_from_id('اللون', ad_info, ad_info_ids) 
    ad_dict['Chasis'] = get_info_from_id('نوع الهيكل', ad_info, ad_info_ids) 
    ad_dict['Ad_type'] = get_info_from_id('نوع الإعلان', ad_info, ad_info_ids)

    # impute ads which didn't have ad_type
    if not ad_dict['Ad_type']:
        ad_dict['Ad_type'] = "معروض للبيع"


    # print("Finished ad dict")
    return ad_dict



def get_res(url, MAX_RETRIES, headers):
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=MAX_RETRIES)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    res = session.get(url, headers=headers)
    
    return res


def scrape_ad(link, headers, sem, sleep=False):
    global all_ad_dicts
    
    sem.acquire(blocking=False)

    if sleep:
        if np.random.random_sample() < 0.5:
            time.sleep(1)

    print(link['href'])
    link_res = get_res(link['href'], max_retries, headers)
    if link_res.status_code == 200:
        link_soup = bs4.BeautifulSoup(link_res.text, features="lxml")
        try:
            ad_dict = make_ad_dict(link_soup, link)
            all_ad_dicts.append(ad_dict)
        except:
            print(link['href'], "doesn't exist anymore")
    
    sem.release()
    
    
def scrape_pages(startPage, endPage, max_retries, headers, max_threads, ad_sleep=False):
    global n_pages
    global n_cars
    
    scraping_threads = []
    for page in range(startPage, endPage):
        url = 'https://www.olx.com.eg/vehicles/cars-for-sale/?page={}'.format(page)
        page_res = get_res(url, max_retries, headers)

        page_soup = bs4.BeautifulSoup(page_res.text, features="lxml")
        page_links = page_soup.select('.ads__item__ad--title')
        
        sem = threading.Semaphore(max_threads)
        for i, link in enumerate(page_links):
            scraping_thread = threading.Thread(target=scrape_ad, args=[link, headers, sem, ad_sleep])
            scraping_threads.append(scraping_thread)
            scraping_thread.start()
            
            n_cars+=1
        n_pages+=1
    
    for i, thread in enumerate(scraping_threads):
        thread.join()


class Command(BaseCommand):
    help = "collect ads"

    def handle(self, *args, **options):
        self.stdout.write("Begin Scraping..")
        for batch in range(1, 500, batch_count):
            scrape_pages(batch, batch+batch_count, max_retries, headers, 5, True)
            if batch % 10 == 0:
                self.stdout.write("%d batches completed" % batch)
                self.stdout.write("%d ads scraped" % len(all_ad_dicts))

        ads_created = 0
        for ad_dict in all_ad_dicts:
            if ad_dict["Ad_type"] == "معروض للبيع" and ad_dict["Pay_type"] in ["كاش", "قابل للبدل"]:
                try:
                    # Ad creation need to be changed to suit the new data model
                    if not Brand.objects.filter(name=ad_dict['Brand']).exists():
                        brand = Brand(name=ad_dict['Brand'])
                        brand.save()
                    else:
                        brand = Brand.objects.filter(name=ad_dict['Brand'])[0]

                    if not Model.objects.filter(name=ad_dict['Model']).exists():
                        model = Model(name=ad_dict['Model'], brand=brand)
                        model.save()
                    else:
                        model = Model.objects.filter(name=ad_dict['Model'])[0]

                    Ad.objects.create(
                        brand=brand,
                        model=model,
                        gov=ad_dict["Governerate"],
                        city=ad_dict["City"],
                        date=ad_dict["Date"],
                        year=ad_dict["Year"],
                        kilos=ad_dict["Kilometers"],
                        pay_type=ad_dict["Pay_type"],
                        transmission=ad_dict["Transmission"],
                        cc=ad_dict["CC"],
                        chasis=ad_dict["Chasis"],
                        features=ad_dict["Features"],
                        color=ad_dict["Color"],
                        price=ad_dict["Price"],
                        url=ad_dict["URL"],
                        description=ad_dict["Description"],
                        imgs= ad_dict["imgs"]
                        )
                    ads_created += 1
                    print('%s - %s - %s added' % (ad_dict["Brand"], ad_dict["Model"], ad_dict["Year"]))
                except:
                    # for info in ad_dict:
                    #     logging.critical(info)
                    #     logging.critical(ad_dict[info])
                    #     logging.critical(type(ad_dict[info]))
                    print("%s - %s - %s couldn't be added" % ((ad_dict["Brand"], ad_dict["Model"], ad_dict["Year"])))
                    logging.critical(ad_dict["URL"])
        self.stdout.write('%d Ads were scraped' % len(all_ad_dicts))
        self.stdout.write('%d Ads were added' % (ads_created))
        self.stdout.write('job complete')

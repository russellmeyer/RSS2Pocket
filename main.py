from datetime import datetime
from datetime import timedelta
from dateutil import parser
from io import BytesIO
import feedparser
import json
import logging
import os
import pandas as pd
import requests
import time
import zipfile


CONSUMER_KEY = os.environ['CONSUMER_KEY']
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
now = datetime.now()


def add_article(consumer_key, access_token, url):
    pocket_url = 'https://getpocket.com/v3/add'
    keys = {'consumer_key': consumer_key,
            'access_token': access_token,
            'url': url,
            'tags': 'feed',
           }
    get_json = requests.post(pocket_url, data = keys)
    get_json = json.loads(get_json.text)
    if get_json.get('status', None) is None:
        logging.error("%s: %s", get_json['error'], get_json['message'])
        exit()
    return get_json['status']


if os.path.exists('rss.txt'):
    with open('rss.txt') as f:
        rss_urls = f.readlines()
else:
    logging.error("rss.txt not exists.")
    exit()


if os.path.exists('rss_database.zip'):
    rss_database = pd.read_csv('rss_database.zip')
else:
    rss_database = pd.DataFrame(columns=["feed_url", "last_saved_item_link", "second_to_last_saved_item_link", "updated_time"])


for rss_url in rss_urls:

    rss_url = rss_url.replace("\n", "")
    if rss_url.startswith("#") or (rss_url == ""): continue

    logging.info("Checking %s", rss_url)
    try:
        resp = requests.get(rss_url, timeout=10.0)
    except requests.ReadTimeout:
        logging.warning("Timeout when reading feed: %s", rss_url)
        continue
    except requests.ConnectionError:
        logging.warning("Cannot access feed: %s", rss_url)
        continue
    except Exception as e:
        logging.error("Unexpected error: %s", str(e))
        continue
    content = BytesIO(resp.content)
    Feed = feedparser.parse(content)

    flag_first_run = False
    if rss_url not in rss_database["feed_url"].values:
        rss_database.loc[-1] = {"feed_url": rss_url, "last_saved_item_link": None, "second_to_last_saved_item_link": None, "updated_time": None}
        rss_database.index = rss_database.index + 1
        flag_first_run = True

    idx = rss_database[rss_database["feed_url"] == rss_url].index.values[0]
    last_link = rss_database[rss_database["feed_url"] == rss_url]["last_saved_item_link"].values[0]
    second_to_last_link = rss_database[rss_database["feed_url"] == rss_url]["second_to_last_saved_item_link"].values[0]

    for entry in Feed.get('entries', []):
        if (entry.link != last_link) and (entry.link != second_to_last_link):

            entry_published_time =  entry.get('published', None)
            logging.info("Article Info:\n"\
                         "\tTitle: %s\n"\
                         "\tPublished time: %s\n"\
                         "\tLink: %s", entry.title, entry_published_time, entry.link)

            if add_article(CONSUMER_KEY, ACCESS_TOKEN, entry.link):
                if rss_database[rss_database["feed_url"] == rss_url]["updated_time"].values[0] != now:
                    rss_database.loc[idx, "second_to_last_saved_item_link"] = last_link
                    rss_database.loc[idx, "last_saved_item_link"] = entry.link
                    rss_database.loc[idx, "updated_time"] = now
                logging.info("Article added")
            else:
                logging.warning("Article not added: %s", entry.link)

            if flag_first_run: break

        else:
            break

rss_database.sort_values("feed_url").to_csv('rss_database.csv', index=False)

with zipfile.ZipFile('rss_database.zip', 'w') as zf:
    zf.write('rss_database.csv')

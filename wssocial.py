#!/usr/bin/python3
import argparse
import logging
import json
import os
from time import strftime
# local imports
from src.common import Info_type, download_files, cache_scrape_func, get_items_from_url
from src.twitter_context import twitter_context
from src.bsky_context import bsky_context

LOG_LEVEL = logging.INFO
CONFIG_FILE = "config.json"


def read_defaults(path:str):
    with open(path, "r") as f:
        res = json.load(f)
    cfile = os.path.expanduser(res["cookie_path"]) 
    if not os.path.exists(cfile):
        raise Exception(f"Cookie path: {cfile} does not exist")
    opath = res["out_path"]
    if not os.path.exists(opath):
        os.mkdir(opath)
    return cfile, opath


def main_api(user:str, site:str, force_not_cache:bool, time:float, use_media:bool, data_type:str):
    # get defaults and variousd ata
    cookie_path, out_path = read_defaults(CONFIG_FILE)

    # Filling/Parsing all parameters
    if data_type == "tweets":
        info_type = Info_type.TWEETS
    elif data_type == "images":
        info_type = Info_type.IMAGES
    elif data_type == "followers":
        info_type = Info_type.FOLLOWERS
    else:
        logging.error(f"Can't get '{data_type}', has not been implemented/doesn't exist!")
        return 1

    if site == "twitter":
        url = "https://x.com/" + user
        if use_media and info_type == Info_type.IMAGES:
            url += "/media"
        if info_type == Info_type.FOLLOWERS:
            if user != "": url += "/"
            url += "following"
        context = twitter_context(user, info_type=info_type, 
                use_media=use_media, high_quality=True, timeout=time)
    elif site == "bsky":
        url = "https://bsky.app/profile/" + user
        if info_type == Info_type.FOLLOWERS:
            logging.warning("Can't get followers, since it is not implemented for bsky backend yet!")
        context = bsky_context(user, info_type=info_type, 
                use_media=use_media, high_quality=True, timeout=time)
        cookie_path = "" # bsky doesnt require cookies
    else:
        logging.error(f"{site} has no implemented backend!")
        return 1

    # Getting Data
    if info_type == Info_type.IMAGES:
        cache_scrape_func(url, context, bypass_cache=force_not_cache, 
                cache_entire_source=False, cookie_path=cookie_path)
    else:
        get_items_from_url(url, cookie_path, context)

    # Collecting/Saving data
    stuff = context.get_data()
    n = len(stuff)
    logging.info(f"We found: {n} {data_type}")
    if n > 0:
        if info_type == Info_type.IMAGES:
            filenames = context.get_filenames()
            out_dir = os.path.join(out_path, user)
            logging.info(f"Outputing to: {out_dir}")
            download_files(stuff, out_dir, filenames)
            logging.info(f"Finished downloading images.")
        else:
            if user == "": user = "home"
            out_file = os.path.join(out_path, f"{data_type}_{site}_{user}.json") 
            logging.info(f"Outputing to: {out_file}")
            with open(out_file, "w") as file:
                now = strftime("%H:%M:%S-%d/%m/%Y")
                file.write("{\n\"date\" : \"" + now + "\",\n")
                file.write(f"\"{data_type}\" : [\n")
                for i, element in enumerate(stuff):
                    json.dump(element, file, indent=4)
                    if i < n-1: file.write(", \n")
                file.write("]\n}")
            logging.info(f"All {data_type} have been saved.")
    else:
        logging.info(f"Nothing to download/save.")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='main', description='Downloads data/images from twitter user.')
    parser.add_argument('-u', '--user', type=str, help="Username from which we download data, set empty to set it to home tab")
    parser.add_argument('-f', '--force', default=False, action='store_true', help="Force download all tweets/images, instead of using cache.")
    parser.add_argument('-t', '--time', default=10*60., type=float, help="Maximum time the program will use to download data.") 
    parser.add_argument('-m', '--media', default=True, action='store_true', help="Use media tab when getting images.") 
    parser.add_argument('-g', '--get', default="tweets", type=str, choices=["tweets", "images", "followers"], help="What type of data to download.") 
    parser.add_argument('-s', '--site', default="twitter", type=str, choices=["twitter", "bsky"], help="Which site to download the data from") 
    args = parser.parse_args()

    # Set logger
    fmt = "[%(levelname)s] %(message)s"
    logging.basicConfig(level=LOG_LEVEL, format=fmt)

    # Call the function
    user = "" if args.user == None else args.user
    main_api(user, args.site, args.force, args.time, args.media, args.get)

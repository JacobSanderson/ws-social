import os
import time
import requests
import concurrent.futures
import logging
import dataclasses
from enum import Enum
# thirdparty
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

class Info_type(Enum):
    IMAGES = 0
    TWEETS = 1
    FOLLOWERS = 2

@dataclasses.dataclass
class socialmedia_context:
    user:str = ""
    timeout:float = 600.
    use_media:bool = True
    high_quality:bool = True
    info_type:Info_type = Info_type.TWEETS
    data:list = dataclasses.field(default_factory=list)
    max_reloads:int = 3
    
    def pre_process(self, browser:WebDriver) -> bool:
        return True

    def process(self, browser:WebDriver) -> bool:
        logging.error("Implement process function when deriving from this class")
        return False

    def post_process(self, browser:WebDriver) -> bool:
        return True

    def get_data(self):
        return self.data

    def retry(self, browser:WebDriver, panic_str:str):
        time.sleep(0.5)
        reload_times = 0
        # If panic, reload
        while browser.page_source.find(panic_str) != -1:
            if reload_times > self.max_reloads:
                logging.error(f"Max reloads reached: {self.max_reloads}, shutting down")
                return False
            reload_times += 1
            logging.info(f"Refreshing: {reload_times}")
            browser.refresh()
        return True

def get_cookie_from_file(filename:str) -> list:
    # Check if filename exists
    if not os.path.exists(filename):
        return []
    filestr = open(filename).read()
    cookies = []
    # Parse the file
    for line in filestr.split("\n"):
        if line == "":
            continue
        if line[0] == "#":
            continue
        fields = line.split("\t")
        cookie = {}
        cookie["domain"] = fields[0] 
        cookie["secure"] = True if fields[1] == "TRUE" else False
        cookie["path"] = fields[2] 
        cookie["httpOnly"] = True if fields[3] == "TRUE" else False 
        cookie["expiry"] = int(fields[4])
        cookie["name"] = fields[5] 
        cookie["value"] = fields[6]
        cookies.append(cookie)
    return cookies


def continuously_scroll(browser:WebDriver, timeout:float, find_func, *args):
    """
    This function continuously_scroll scroll the browser in current site
    each time it does a scroll operation it calls func(browser.page_source, *args)
    in order to parse the site.
    Assumes func returns a list

    Arguments:
        timeout:float - Time passing scrolling
    """
    start = time.time()
    last_page_source, diff = "", 0.0
    timestamp = time.time()
    # To ensure no repeats
    things = []
    while (diff <= timeout):
        # Scroll
        for _ in range(5):
            ActionChains(browser).send_keys(Keys.PAGE_DOWN).perform()
        # Do parsing
        res = find_func(browser.page_source, *args)
        for item in res:
            if item in things:
                continue
            things.append(item)
        # Check if already at the end of feed
        if last_page_source != browser.page_source:
            last_page_source = browser.page_source
            timestamp = time.time()
        else:
            if (time.time() - timestamp > 8.0):
                print("\n[INFO] Done early, exiting!", end="")
                break
        # Show info
        diff = time.time() - start
        print(f"[INFO] Time elapsed: {diff:.1f}s; Found: {len(things)} things\r", end="")
    print("")
    return list(things), last_page_source


def download_file(url:str, out_dir:str, name):
    """Download url to out_dir"""
    if url == "":
        logging.error("Can't download empty url")
        return
    filepath = os.path.join(out_dir, name)
    # If already downloaded do not download again
    if os.path.exists(filepath):
        logging.error("Already downloaded that file")
        return
    # Get file
    data = requests.get(url)
    if data.ok:
        with open(filepath, "wb") as f:
            f.write(data.content) 
    else:
        logging.error(f"Couldn't Download {url}!")


def download_files(urls:list, out_dir:str, names:list):
    """
    Download all urls (if urls are files) using various threds
    You must provide a filename for each url provided
    """
    # Making sure inputs makes sense
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    if len(urls) == 0:
        logging.info("Nothing to download!")
        return
    if list(names) == 0:
        names = urls
    # Cap # of threads
    if len(urls) < 16:
        size = len(urls)
    else:
        size = 16
    # Download concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=size) as executor:
        futures = {executor.submit(download_file, url, out_dir, name):url for url, name in zip(urls, names)}
        count = 0
        for _ in concurrent.futures.as_completed(futures):
            count += 1
            print(f"[INFO] Downloading {count}/{len(urls)}\r", end="")
        print("")


def cache_source(source:str, url:str, cache_dir:str = "./cache/"):
    n = len("https://")
    filename = url[n:] + ".html"
    filename = filename.replace("/", "::")
    with open(cache_dir + filename, "w") as file:
        file.write(source)


def get_cache_source(url:str, cache_dir:str = "./cache/"):
    n = len("https://")
    filename = url[n:] + ".html"
    filename = cache_dir + filename.replace("/", "::")
    if os.path.exists(filename):
        return open(filename, "r").read()
    else:
        return ""


def cached_get_url(url:str, cache_dir:str = "./cache/"):
    source = get_cache_source(url, cache_dir)
    if source == "":
        response = requests.get(url)
        if response.ok:
            source = response.content.decode("latin 1")
            cache_source(source, url, cache_dir)
        else:
            logging.error(f"{response.status_code}: {response.text}")
            raise Exception("a")
    return source
    

def cache_scrape_func(url:str, context, *, bypass_cache:bool=False, action_func = None,
        cache_entire_source:bool=False, cookie_path:str=""):
    """
    This calls get_items_from_url_using_func(..., find_func, *func_args) if the site or data hasn't been cached yet
    This function assumes that find_func returns a list
    It writes the cache in ./cache/

    Keyword Arguments:
        bypass_cache:bool - Ignores cache, functionally the same as just calling scrape_func and cache the result
        cache_entire_source:bool - Wether to cache the site or the result of scraping
    """
    ext = ".html" if cache_entire_source else ".data"
    n = len("https://")
    url_cache_path = "./cache/" + url.replace("/", "-") + ext
    if not os.path.exists("./cache"):
        os.mkdir("cache")
    # Check if in cache
    if os.path.exists(url_cache_path) and (not bypass_cache):
        if cache_entire_source:
            # Data is the source
            data = open(url_cache_path, "r").read() 
        else:
            with open(url_cache_path, "r") as file:
                data = file.read().split("\n")
        context.data = data
    else:
        # Actually get items using browser
        if action_func == None:
            action_func = lambda x: x
        get_items_from_url(url, cookie_path, context)
        # Cached it
        with open(url_cache_path, "w") as file:
            for element in context.data:
                file.write(str(element)+"\n")


def get_items_from_url(url:str, cookie_path:str, context):
    """
    Opens a selenium browser, gets to url (using cookie if necessary) using context
    then continuously_scroll the url using func(page_source, *args) to parse the site
    to continuously collect whatever items we want.
    """
    # Create browser
    options = webdriver.FirefoxOptions()
    browser = webdriver.Firefox(options=options)
    
    # Extract all webpage
    logging.info(f"Opening website")
    # Add the cookie
    if os.path.exists(cookie_path):
        base_url = url[:url.find("/", len("https://"))]
        browser.get(base_url)
        browser.implicitly_wait(5.0)
        # Add the cookie in the base url
        # Make sure we actually are in the correct url
        cookies = get_cookie_from_file(cookie_path)
        logging.info(f"Inserting cookie")
        for cookie in cookies:
            browser.add_cookie(cookie)
        browser.get(url)
        browser.implicitly_wait(5.0)
    else:
        # Assume it doesn't need cookies
        browser.get(url)
    # Ensure we are on the page
    browser.implicitly_wait(5.0)

    # Do any special treatement on the page before scrolling
    # like reloading if not responding, clicking buttons and so on
    ok = context.pre_process(browser)
    if not ok:
        logging.error("Error in pre_process stage, exiting")
        browser.close()
        return

    # Now that we are going to work
    ok = context.process(browser)
    if not ok:
        logging.error("Error in process stage, exiting")
        browser.close()
        return

    # Stop working, and do final cleanout or whatever
    ok = context.post_process(browser)
    if not ok:
        logging.error("Error in post_process stage, exiting")
        browser.close()
        return
    
    browser.close()
    

#################################################
# Test functions
#################################################
def test_url_root():
    url = "https://bsky.app/profile/badempanada.com"
    base_url = url[:url.find("/", 9)] # len( "https://" )
    logging.info(f"{base_url}")

if __name__ == "__main__":
    test_url_root()

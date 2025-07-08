import logging
import time
# thirdparty
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
# local imports
from src.common import Info_type, continuously_scroll, socialmedia_context

def find_images_bsky(page_source:str, author:str):
    soup = BeautifulSoup(page_source, features="lxml")
    posts = soup.find_all("div", {"data-testid" : f"feedItem-by-{author}"})
    images = []
    for post in posts:
        main_div = post.find("div", {"data-testid" : "contentHider-post"})
        # If not found skip
        if main_div.img == None:
            continue
        images.append( main_div.img.get("src") )
    # remove tab
    return images

class bsky_context(socialmedia_context):
    def pre_process(self, browser:WebDriver) -> bool:
        if not self.retry(browser, "Page Not Found"):
            return False
        if self.info_type == Info_type.IMAGES and self.use_media:
            time.sleep(0.5)
            # Click media tab
            # butt_media = browser.find_element("div", {"data-testid": "profilePager-selector-1"})
            try:
                posx, posy = 830, 370
                ActionChains(browser).move_by_offset(posx, posy).click(None).perform()
            except NoSuchElementException:
                logging.error("Couldn't find media button")
                return False
        return True

    def process(self, browser:WebDriver) -> bool:
        if self.info_type == Info_type.IMAGES:
            f = find_images_bsky
            args = (self.user, )
            self.data, _ = continuously_scroll(browser, self.timeout, f, *args)
        else:
            logging.error(f"{self.info_type} not implemented for bsky yet!")
            return False
        return True

    def get_filenames(self) -> list[str]:
        return self.data
        

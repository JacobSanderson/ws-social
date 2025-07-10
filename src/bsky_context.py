import logging
import json
import time
# thirdparty
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
# local imports
from src.common import Info_type, continuously_scroll, socialmedia_context


def handle_text(tag):
    buff = ""
    for child in tag.children:
        if isinstance(child, str):
            buff += child
            continue
        buff += child.string
    return buff
    

def find_tweets(page_source:str, author:str) -> list[dict]:
    soup = BeautifulSoup(page_source, features="lxml")

    def get(tag, id:str, name:str):
        return tag.find(id, attrs={"data-testid":name})
    
    base = soup.find("div", attrs={"data-testid" : "customFeedPage"})
    if base == None:
        base = soup
    tweets = []
    for root in base.find_all("div"):
        handle = root.get("data-testid")
        if handle == None: continue
        if not handle.startswith("feedItem-by-"): continue
        handle = handle.removeprefix("feedItem-by-")
        if (author != "") and (handle != author): continue
        post = get(root, "div", "contentHider-post")
        if post == None: continue

        res = {}
    
        # Metadata
        res["context"] = root.get("data-feed-context") 
        temp = root.find("a", attrs={"aria-label": "View profile"})
        res["name"] = temp.string[1:-1]
        res["handle"] = handle
        res["date"] = temp.parent.parent.parent.next_sibling.get("data-tooltip")

        # Content
        for child in post.children:
            if child.get("data-testid") == "postText":
                res["text"] = handle_text(child)
                continue
            others = list(child.div.children)
            for div in others:
                quote = div.find("div", attrs={"role":"link"})
                if quote != None:
                    res["quoting"] = quote.get("aria-label")
                    continue
                img = div.find("img")
                if img != None:
                    res["img"] = img.get("src")
                    res["img_alt"] = img.get("alt")
                    continue
                video = div.find("video")
                if video != None:
                    res["has_video"] = True
                    res["video_url"] = video.get("src")
                # asssume it has video
                res["has_video"] = True
                res["video_url"] = None

        if res.get("text") == None:
            res["text"] = None
        if res.get("img") == None:
            res["img"] = None
            res["img_alt"] = None
        if res.get("quoting") == None:
            res["quoting"] = None
        if res.get("has_video") == None:
            res["has_video"] = False
            res["video_url"] = None

        # Metrics
        butt = get(root, "button", "likeBtn").get("aria-label").removeprefix("Like (")
        butt = butt[:butt.find(" ")].replace(",", "")
        res["like_count"] = int(butt)
        butt = get(root, "div", "repostCount")
        res["repost_count"] = butt.string if butt != None else 0
        butt = get(root, "button", "replyBtn").div
        res["comment_count"] = butt.string if butt != None else 0
        
        tweets.append(res)
    return tweets


def find_images_bsky(page_source:str, author:str) -> list[str]:
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
        args = (self.user, )
        if self.info_type == Info_type.TWEETS:
            f = find_tweets
        elif self.info_type == Info_type.IMAGES:
            f = find_images_bsky
        else:
            logging.error(f"{self.info_type} not implemented for bsky yet!")
            return False

        self.data, _ = continuously_scroll(browser, self.timeout, f, *args)
        return True

    def get_filenames(self) -> list[str]:
        return self.data
        

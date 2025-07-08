import logging
import time
import dataclasses
# thirdparty
from selenium.webdriver.remote.webdriver import WebDriver
from bs4 import BeautifulSoup
# local imports
from src.common import Info_type, continuously_scroll, socialmedia_context

logger = logging.getLogger(__name__)

def get_text_with_emojis(tag) -> str:
    text = ""
    for el in tag.children:
        s = str(el)
        if s.find("<img") != -1: # emojis
            icon = el.get("alt")
            if icon != None:
                text += icon
        elif s.find("<div") != -1: # handles
            text += el.span.a.string
        elif s.find("<a") != -1: # external link and hashtags
            if el.name == "a":
                text += el.get("href")
            elif el.name == "span": # hashtag
                text += el.a.string
        elif s.find("<span") != -1: # plaintext
            tempstr = el.string
            if tempstr == None:
                continue
            tempstr = tempstr.replace("\n", "\\n")
            tempstr = tempstr.replace('"', "''")
            text += tempstr.replace("\t","\\t")
    return text


def get_stats(stats:str) -> dict[str, int]:
    res = {}
    types = ["replies", "reposts", "likes", "bookmarks", "views"]
    for item in stats.split(", "):
        for t in types:
            if item.endswith(t):
                res[t] = int(item.removesuffix(t))
                break
    return res


def find_tweets(page_source:str) -> list[dict]:
    soup = BeautifulSoup(page_source, features="lxml")
    posts = soup.find_all("article", {"data-testid" : "tweet"})
    posts = posts[:3]
    tweets = []
    for post in posts:
        ctweet = {}
        # Check if quote_tweet
        tag = post.find_all("div", {"data-testid" : "Tweet-User-Avatar"})
        if len(tag) > 1:
            ctweet["tweet_type"] = "quote"
        tag = post.find("span", {"data-testid" : "socialContext"})
        if tag != None:
            ctweet["tweet_type"] = "repost"
            tag = tag.find_parent()
            if tag != None:
                ctweet["repost_handle"] = tag.get("href")
            else:
                ctweet["repost_handle"] = ""
        tag = post.find("div").find("div").find("div").find("div").find("div").find("div")
        if tag != None:
            ctweet["tweet_type"] = "reply"
        if ctweet.get("tweet_type") == None:
            ctweet["tweet_type"] = "tweet"

        # Creator and time header (doesn't exist for ads)
        a_tags_header = post.find("div", {"data-testid" : "User-Name"}).find_all("a", {"role" : "link"})
        if len(a_tags_header) == 3:
            try:
                ctweet["name"] = get_text_with_emojis( a_tags_header[0].span )
                ctweet["handle"] = a_tags_header[1].span.string[1:]
                ctweet["date"] = a_tags_header[2].time.get("datetime")
            except Exception as e:
                ctweet["name"] = ""
                ctweet["handle"] = ""
                ctweet["date"] = ""
                logger.error(f"Can't parse {a_tags_header}\n\t> {e}")
        else:
            # Ignore adds by default
            ctweet["tweet_type"] = "ad"
            continue

        tag = post.find("div", {"data-testid" : "tweetText"})
        if tag != None: ctweet["text"] = get_text_with_emojis(tag)
        else: ctweet["text"] = ""

        tag = post.find("div", {"data-testid" : "card.wrapper"})
        if tag != None: ctweet["ext_link"] = tag.find("a").get("href")
        else: ctweet["ext_link"] = ""

        tag = post.find("div", {"data-testid" : "videoComponent"})
        if tag != None: ctweet["has_video"] = True
        else: ctweet["has_video"] = False

        tag = post.find("div", {"data-testid" : "tweetPhoto"})
        if tag != None:
            if tag.img != None:
                ctweet["img_link"] = tag.img.get("src")
            else:
                ctweet["img_link"] = ""
        else:
            ctweet["img_link"] = ""

        tag = post.find("div", {"class": "css-175oi2r", "role": "group"})
        if tag != None: ctweet["stats"] = get_stats(tag.get("aria-label"))
        else: ctweet["stats"] = {}

        links = []
        ctweet["quote_link"] = ""
        for el in post.find_all("a", {"role" : "link"}):
            temp_2 = el.get("href")
            if temp_2 == None:
                continue
            index = temp_2.find("/status")
            if index == -1:
                continue
            link = temp_2[1:]
            if link.find(ctweet["handle"]) == -1:
                ctweet["quote_link"] += link
            links.append(link)
        ctweet["url"] = "https://x.com/" + links[0]
        if ctweet["tweet_type"] == "quote":
            ctweet["quote_link"] += links[1] 
            ctweet["quote_link"] = "https://x.com/" + ctweet["quote_link"]

        tweets.append(ctweet)
    return tweets


def find_following_users(page_source:str) -> list[dict]:
    soup = BeautifulSoup(page_source, features="lxml")
    posts = soup.find_all("button", {"data-testid" : "UserCell"})
    users = []
    for post in posts:
        # Assume all have the same format
        header = post.find_all("a", {"role" : "link"})
        handle = header[2].span.string[1:]
        name = get_text_with_emojis(header[1].span) 
        user = {}
        user["handle"] = handle
        user["name"] = name
        users.append(user)
    return users


def find_images_post(page_source:str, author_filter:str) -> list[str]:
    soup = BeautifulSoup(page_source, features="lxml")
    # Find tweets
    posts = soup.find_all("article", {"data-testid" : "tweet"})
    images = []
    for post in posts:
        # Ignore posts with no images
        img_tags = post.find_all("img")
        if len(img_tags) <= 1:
            continue
        # Ignore reposts
        a_tags = post.find_all("a", {"role" : "link"})
        if len(a_tags[0].find_all("span")) != 0: 
            continue
        # Fill data
        posible_owners = [str(o.get("href")[1:]) for o in a_tags]
        if len(posible_owners) <= 2:
            owner = posible_owners[0]
        else:
            owner = posible_owners[1]
        images_tags = soup.find_all("img")
        for img in images_tags:
            src = str(img.get("src"))
            if (src.find("twimg") != -1) and (src.find("media") != -1):
                if owner == author_filter:
                    images.append(f"{src}")
    return images


def find_images_media(page_source:str) -> list[str]:
    soup = BeautifulSoup(page_source, features="lxml")
    a_tags = soup.find_all("a", {"role" : "link"})
    images = []
    for a_tag in a_tags:
        # random edge case
        if len(a_tag.find_all("span")) > 0:
            continue
        # ignore tags without images
        if len(a_tag.find_all("img")) == 0:
            continue
        # multiple images case
        if len(a_tag.find_all("svg")) > 0:
            link = a_tag.get("href")
            link = "https://x.com" + link[:link.find("/photo")]
            images.append( f"*{link}" )
            continue
        # single image case
        src = a_tag.find("img").get("src")
        if (src.find("twimg") != -1) and (src.find("media") != -1):
            images.append(f"{src}")
    # remove tab
    return images


class twitter_context(socialmedia_context):
    def pre_process(self, browser:WebDriver) -> bool:
        return self.retry(browser, "Try reloading")

    def process(self, browser:WebDriver) -> bool:
        # Select correct function
        args = ()
        if self.info_type == Info_type.IMAGES:
            if self.use_media:
                f = find_images_media
            else:
                f = find_images_post
                args = (self.user, )
        elif self.info_type == Info_type.TWEETS:
            f = find_tweets
        elif self.info_type == Info_type.FOLLOWERS:
            f = find_following_users
        else:
            logging.error(f"{self.info_type} has no implemented find_func")
            return False
        self.data, _ = continuously_scroll(browser, self.timeout, f, *args)
        return True

    def post_process(self, browser:WebDriver) -> bool:
        if self.info_type != Info_type.IMAGES:
            return True
        # Check if having more images to get
        new_images = []
        count = 0
        for url in self.data:
            print(f"[INFO] Multiple files: {count}\r", end="")
            if url[0] == "*": # Multiple image case
                browser.get(url[1:])
                time.sleep(2.)
                imgs = find_images_post(browser.page_source, self.user)
                for img in imgs:
                    new_images.append(self.__parse_img_url(img))
                count += 1
            else:
                new_images.append(self.__parse_img_url(url))
        self.data = new_images
        return True
    
    def __parse_img_url(self, url:str) -> str:
        if self.high_quality:
            return url[:url.find("&")]
        return url

    def get_filenames(self) -> list[str]:
        names = []
        if self.info_type == Info_type.IMAGES:
            for k, url in enumerate(self.data):
                temp = url.find("format=")
                if temp != -1:
                    name = f"{self.user}_{k:06d}" # url[url.rfind("/")+1:temp-1]
                    ext = url[temp+7:]
                    f_index = ext.find("&")
                    if f_index != -1:
                        ext = ext[:f_index]
                    ext = "." + ext
                    names.append( name + ext )
                else:
                    names.append( url )
        return names


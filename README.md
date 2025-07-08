# WebScrape-Social

Webscrape utility to get data from social media apps.

Currently only backends are:
- twitter
- bsky


# Requirements

- selenium: for getting pages
- BeautifulSoup: for parsing html
- requests: to download files from the internet

# Usage

0. Download this repo.
1. Get the cookies from twitter using [an extension like this one](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/).
2. Write the path to the cookie file in `config.json`.
3. Make sure you pip install all requirements previously mentionend.
4. Run the following command in your terminal
```bash
 ./wssocial.py -h
```
If all runs well, you're good to go. The help message should tell you how to use it.


# Notes

**USE THIS SCRIPT AT YOUR OWN RISK, IT MAY BAN YOU FROM CERTAIN SOCIAL MEDIA SITES**

This scripts has been written in python 3.10, and has only been testes on a linux machine.

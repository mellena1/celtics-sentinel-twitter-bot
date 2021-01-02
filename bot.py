from datetime import datetime, timedelta, timezone
import json
import logging
import os
from typing import Callable, List, Dict

import boto3
import feedparser
from twitter import OAuth, Twitter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


BLOG_URL = "https://www.celticscentral.blogspot.com.celticscentral.com"
ATOM_FEED = f"{BLOG_URL}/feeds/posts/default"


def get_creds() -> Dict[str, str]:
    env = os.environ.get("ENVIRONMENT", "local")
    if env == "local":
        with open("credentials.json") as f:
            return json.load(f)
    elif env == "lambda":
        s3 = boto3.resource("s3")
        obj = s3.Object(
            bucket_name="celtics-sentinel-twitter-bot", key="credentials.json"
        )
        return json.load(obj.get()["Body"])
    else:
        raise ValueError(f'Invalid env: "{env}"')


# get creds for Twitter API and make client
creds = get_creds()
oauth = OAuth(
    creds["ACCESS_TOKEN"],
    creds["ACCESS_SECRET"],
    creds["CONSUMER_KEY"],
    creds["CONSUMER_SECRET"],
)
twit_client = Twitter(auth=oauth)
TWITTER_HANDLE = twit_client.account.verify_credentials()["screen_name"]


def get_articles() -> List[Dict[str, any]]:
    """
    gets all articles from our atom feed
    """
    d = feedparser.parse(ATOM_FEED)
    return d["entries"]


def filter_objs_by_time(
    objs: List[any], delta: timedelta, get_datetime_fn: Callable[[any], datetime]
) -> List[any]:
    """
    get all objs that have datetimes <= delta
    """
    now = datetime.now(timezone.utc)

    def article_timedelta(obj: any) -> timedelta:
        return now - get_datetime_fn(obj)

    return list(
        filter(
            lambda x: article_timedelta(x) <= delta,
            objs,
        )
    )


def filter_articles_by_publish_time(
    articles: List[Dict[str, any]], delta: timedelta
) -> List[Dict[str, any]]:
    """
    get all articles that were posted within the last x amount of time (delta)
    """
    return filter_objs_by_time(
        articles,
        delta,
        # 2021-01-01T04:55:00.001-05:00
        lambda x: datetime.strptime(x["published"], "%Y-%m-%dT%H:%M:%S.%f%z"),
    )


def filter_tweets_by_publish_time(
    tweets: List[Dict[str, any]], delta: timedelta
) -> List[Dict[str, any]]:
    """
    get all tweets that were posted within the last x amount of time (delta)
    """
    return filter_objs_by_time(
        tweets,
        delta,
        # Sat Jan 02 02:19:12 +0000 2021
        lambda x: datetime.strptime(x["created_at"], "%a %b %d %H:%M:%S %z %Y"),
    )


def find_tweeted_articles(tweets: List[Dict[str, any]]) -> List[str]:
    """
    find all blog articles posted on our twitter
    """
    articles = []
    for tweet in tweets:
        for url in tweet["entities"]["urls"]:
            if BLOG_URL in url["expanded_url"]:
                articles.append(url["expanded_url"])

    return articles


def handler(event, context):
    """
    get all of our articles, get all of our tweeted articles,
    tweet any articles that haven't been tweeted yet
    """
    # get articles
    articles = get_articles()
    recent_articles = filter_articles_by_publish_time(articles, timedelta(minutes=20))
    logging.info(
        "Found {} recent articles: {}".format(
            len(recent_articles), list(map(lambda x: x["title"], recent_articles))
        )
    )

    # get tweets
    timeline_tweets = twit_client.statuses.user_timeline(
        screen_name=TWITTER_HANDLE, count=200
    )
    recent_tweets = filter_tweets_by_publish_time(
        timeline_tweets, timedelta(minutes=20)
    )
    already_tweeted = find_tweeted_articles(recent_tweets)
    logging.info(
        f"Found {len(already_tweeted)} already tweeted articles: {already_tweeted}"
    )

    # reversed because we want newer articles tweeted last
    for article in reversed(recent_articles):
        link = article["link"]
        # twitter adds this string to the end of the URLs
        if not link.endswith("?spref=tw"):
            link += "?spref=tw"

        if link not in already_tweeted:
            status = article["title"] + " " + link
            logging.info(f"Tweeting: {status}")
            twit_client.statuses.update(status=status)
        else:
            logging.info(f'Article "{article["title"]}" has already been tweeted')


if __name__ == "__main__":
    handler({}, {})

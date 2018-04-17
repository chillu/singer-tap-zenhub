import requests
from singer import metrics
import backoff
import json
import urllib.parse

BASE_URL = "https://api.zenhub.io/"


class RateLimitException(Exception):
    pass

class Zenhub(object):
    """
    Basic Zenhub client
    See https://github.com/ZenHubIO/API
    Rate limited to 100 requests per minute
    """

    def __init__(self, token, logger=None):
        self.token = token
        self.logger = logger

    @backoff.on_exception(backoff.expo, RateLimitException, max_tries=10, factor=2)
    def _get(self, path):
        headers = {
            "X-Authentication-Token": self.token
        }
        url = urllib.parse.urljoin(BASE_URL, path)
        
        if self.logger:
            self.logger(url)

        response = requests.get(url, headers=headers)

        if response.status_code in [403]:
            raise RateLimitException()
        
        response.raise_for_status()

        return response.json()

    def issue(self, repo_id, issue_number):
        path = '/p1/repositories/%s/issues/%s' % (repo_id, issue_number)
        return self._get(path)
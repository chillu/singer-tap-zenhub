import requests
from singer import metrics
import backoff
import json

BASE_URL = "https://api.github.com/graphql"


class RateLimitException(Exception):
    pass

class Github(object):
    """Basic GraphQL client"""

    def __init__(self, token, logger=None):
        self.token = token
        self.max_pages = 50
        self.logger = logger

    @backoff.on_exception(backoff.expo, RateLimitException, max_tries=10, factor=2)
    def query(self, query, variables):
        headers = {
            "Authorization": "bearer %s" % (self.token)
        }
        payload = {
            'query': query,
            'variables': variables
        }

        if self.logger:
            self.logger(json.dumps(payload))

        response = requests.post(BASE_URL, json=payload, headers=headers)

        if response.status_code in [429, 503]:
            raise RateLimitException()
        
        response.raise_for_status()

        return response.json()

    def query_all(self, query, variables, query_name):
        """Query all pagination pages. Relies on an 'after' variable in the query"""
        cursor = None
        nodes = []

        for i in range(self.max_pages):
            variables['after'] = cursor
            data = self.query(query, variables)
            page_info = data['data'][query_name]['pageInfo']
            nodes = nodes + data['data'][query_name]['nodes']

            if(page_info['hasNextPage'] and page_info['endCursor']):
                cursor = page_info['endCursor']
            else:
                break

        return nodes
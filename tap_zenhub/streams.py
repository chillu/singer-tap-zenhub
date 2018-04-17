import singer
from .schemas import IDS
from .clients.github import Github as GithubClient
from .clients.zenhub import Zenhub as ZenhubClient

LOGGER = singer.get_logger()
ZENHUB_BASE_URL = 'https://api.zenhub.io/'

def metrics(tap_stream_id, records):
    with singer.metrics.record_counter(tap_stream_id) as counter:
        counter.increment(len(records))


def write_records(tap_stream_id, records):
    singer.write_records(tap_stream_id, records)
    metrics(tap_stream_id, records)


def get_github_issues(github_client, repos):
    repos_query = ' '.join('repo:%s' % (repo) for repo in repos)
    query = """
query ($queryStr: String!, $after: String) { 
  search(query:$queryStr, first:100, after:$after, type:ISSUE) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ...on Issue {
        id
        number
        url
        lastEditedAt
        closedAt
        repository {
          id
          databaseId
          nameWithOwner
        }
      }
    }
  }
}
"""

    variables = {
      'queryStr': 'is:issue %s' % (repos_query)
    }

    issues = github_client.query_all(query, variables, 'search')

    return issues

def sync_issues(ctx):
    # TODO Replace with canonical id
    tap_stream_id = 'issues'

    repos = ctx.config.get('repos')
    github_client = GithubClient(token=ctx.config.get('github_token'))
    zenhub_client = ZenhubClient(token=ctx.config.get('zenhub_token'))

    github_issues = get_github_issues(github_client, repos)
    for github_issue in github_issues:
        zenhub_issue = zenhub_client.issue(
            # TODO Will be deprecated in July 2018,
            # see https://github.com/ZenHubIO/API/issues/85
            repo_id=github_issue.get('repository').get('databaseId'),
            issue_number=github_issue.get('number')
        )
        record = {
            'repository_name_with_owner': github_issue.get('repository').get('nameWithOwner'),
            'repository_id': github_issue.get('repository').get('id'),
            'issue_number': github_issue.get('number'),
            'estimate_value': zenhub_issue.get('estimate', {}).get('value'),
            'pipeline_name': zenhub_issue.get('pipeline').get('name'),
            'is_epic': zenhub_issue.get('is_epic')
        }
        singer.write_record(tap_stream_id, record)
        with singer.metrics.record_counter(tap_stream_id) as counter:
            counter.increment()
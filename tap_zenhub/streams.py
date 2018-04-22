import singer
from datetime import datetime
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


def get_github_issues(github_client, repos, state="", updated=""):
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
          name
          owner {
            login
          }
        }
      }
    }
  }
}
"""

    variables = {
      'queryStr': 'is:issue %s is:%s updated:%s' % (repos_query, state, updated)
    }

    issues = github_client.query_all(query, variables, 'search')

    return issues

def get_repo_data(github_client, repo):
    query = """
query ($owner: String!, $name: String!) { 
    repository(owner:$owner, name:$name) {
        id
        databaseId
        name
        owner {
            login
        }
    }
}
"""
    owner,name = repo.split('/')
    data = github_client.query(query, {'owner': owner, 'name': name})
    return data['data']['repository']

def sync_issues(ctx):
    # TODO Replace with canonical id
    tap_stream_id = 'issues'

    repos = ctx.config.get('repos')
    github_client = GithubClient(token=ctx.config.get('github_token'))
    zenhub_client = ZenhubClient(token=ctx.config.get('zenhub_token'))

    # Get issues for all boards
    for repo in repos:
        repo_data = get_repo_data(github_client, repo)
        owner,name = repo.split('/')
        # TODO Will be deprecated in July 2018,
        # see https://github.com/ZenHubIO/API/issues/85
        board = zenhub_client.board(repo_data.get('databaseId'))
        for pipeline in board.get('pipelines'):
            for issue in pipeline.get('issues'):
                record = {
                    'id': '-'.join([
                        repo_data.get('id'),
                        str(issue.get('issue_number'))
                    ]),
                    'repository_name': name,
                    'repository_owner': owner,
                    'repository_id': repo_data.get('id'),
                    'issue_number': issue.get('issue_number'),
                    'estimate_value': issue.get('estimate', {}).get('value'),
                    'pipeline_name': pipeline.get('name'),
                    'is_epic': issue.get('is_epic')
                }
                singer.write_record(tap_stream_id, record)
                with singer.metrics.record_counter(tap_stream_id) as counter:
                    counter.increment()

    # Get all issues closed since the last sync (by updated date).
    # The Zenhub "board" API doesn't include those, but they are still relevant for statistics
    query_updated_filter = ""
    last_updated = ctx.get_bookmark(['issues', 'last_updated'])
    if last_updated:
        query_updated_filter = ">" + last_updated

    github_issues = get_github_issues(github_client, repos, state="closed", updated=query_updated_filter)
    for github_issue in github_issues:
        zenhub_issue = zenhub_client.issue(
            # TODO Will be deprecated in July 2018,
            # see https://github.com/ZenHubIO/API/issues/85
            repo_id=github_issue.get('repository').get('databaseId'),
            issue_number=github_issue.get('number')
        )
        record = {
            'id': '-'.join([
                github_issue.get('repository').get('id'),
                str(github_issue.get('number'))
            ]),
            'repository_name': github_issue.get('repository').get('name'),
            'repository_owner': github_issue.get('repository').get('owner').get('login'),
            'repository_id': github_issue.get('repository').get('databaseId'),
            'issue_number': github_issue.get('number'),
            'estimate_value': zenhub_issue.get('estimate', {}).get('value'),
            'pipeline_name': zenhub_issue.get('pipeline').get('name'),
            'is_epic': zenhub_issue.get('is_epic')
        }
        singer.write_record(tap_stream_id, record)
        with singer.metrics.record_counter(tap_stream_id) as counter:
            counter.increment()

    # Remember where we left off,
    # to avoid querying potentially thousands of closed issues from both
    # Zenhub and Github
    ctx.set_bookmark(['issues', 'last_updated'], datetime.utcnow())
    ctx.write_state()
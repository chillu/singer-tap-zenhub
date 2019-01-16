import singer
from datetime import datetime
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

    query_str_parts = [
        'is:issue ' + repos_query,
        'is:' + state
    ]
    if updated:
         query_str_parts.append("updated:" + updated)

    variables = {
      'queryStr': " ".join(query_str_parts)
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

def sync_issues(config, state):
    bookmarks = state.get('bookmarks').get('issues') if state else {}
    repos = config.get('repos')
    github_client = GithubClient(token=config.get('github_token'))
    zenhub_client = ZenhubClient(token=config.get('zenhub_token'))

    all_issues = []

    # Resolve repo names to ids
    repos_with_data = {}
    for repo in repos:
        LOGGER.info(repo + ': Get repo data')
        repos_with_data[repo] = get_repo_data(github_client, repo)

    # Get issues for all boards
    for repo, repo_data in repos_with_data.items():
        owner,name = repo.split('/')
        # TODO Will be deprecated in July 2018,
        # see https://github.com/ZenHubIO/API/issues/85
        LOGGER.info(repo + ': Get zenhub board')
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
                    'repository_database_id': repo_data.get('databaseId'),
                    'issue_number': issue.get('issue_number'),
                    'estimate_value': issue.get('estimate', {}).get('value'),
                    'pipeline_name': pipeline.get('name'),
                    'is_epic': issue.get('is_epic')
                }
                all_issues.append(record)
                # singer.write_record('issues', record)
                # with singer.metrics.record_counter('issues') as counter:
                #     counter.increment()

    # Get all issues closed since the last sync (by updated date).
    # The Zenhub "board" API doesn't include those, but they are still relevant for statistics.
    # Do this for each individual repo in order to track last_updated per repo,
    # and support later additions of new repos to the config
    for repo, repo_data in repos_with_data.items():
        query_updated_filter = ""
        last_updated = bookmarks.get(repo + '.last_updated')
        if last_updated:
            query_updated_filter = ">" + last_updated

        if last_updated:
            LOGGER.info(repo + ': Get closed Github issues since ' + last_updated)
        else:
            LOGGER.info(repo + ': Get closed Github issues')

        github_issues = get_github_issues(github_client, [repo], state="closed", updated=query_updated_filter)
        for github_issue in github_issues:
            LOGGER.info(repo + ': Get Zenhub issue for #' + str(github_issue.get('number')))
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
                'repository_id': github_issue.get('repository').get('id'),
                'repository_database_id': github_issue.get('repository').get('databaseId'),
                'issue_number': github_issue.get('number'),
                'estimate_value': zenhub_issue.get('estimate', {}).get('value'),
                'pipeline_name': zenhub_issue.get('pipeline').get('name'),
                'is_epic': zenhub_issue.get('is_epic')
            }
            all_issues.append(record)
            singer.write_record('issues', record)
            # with singer.metrics.record_counter('issues') as counter:
            #     counter.increment()

            # Remember where we left off for this repo,
            # to avoid querying potentially thousands of closed issues from both Zenhub and Github
            ctx.set_bookmark(['issues', repo + '.last_updated'], datetime.utcnow())

    # Get events for each issue
    # Needs to include all processed issues,
    # since Zenhub's API doesn't allow filtering by created_at,
    # and we can't infer from Github's updated status if Zenhub data has changed.
    # Does not closed issues older than last_updated.
    # TODO Recommend using webhooks for collection instead
    for issue in all_issues:
        repo = '/'.join([issue.get('repository_owner'), issue.get('repository_name')])
        LOGGER.info(repo + ': Get Zenhub issue events for #' + str(issue.get('issue_number')))
        issue_events = zenhub_client.issue_events(
            repo_id=issue.get('repository_database_id'),
            issue_number=issue.get('issue_number')
        )
        for issue_event in issue_events:
            record = {
                'id': '-'.join([
                    issue.get('id'),
                    issue_event.get('created_at')
                ]),
                'repository_name': issue.get('repository_name'),
                'repository_owner': issue.get('repository_owner'),
                'repository_id': issue.get('repository_id'),
                'repository_database_id': issue.get('repository_database_id'),
                'issue_number': issue.get('issue_number'),
                'from_estimate_value': issue_event.get('from_estimate', {}).get('value'),
                'to_estimate_value': issue_event.get('to_estimate', {}).get('value'),
                'from_pipeline_name': issue_event.get('from_pipeline', {}).get('name'),
                'to_pipeline_name': issue_event.get('to_pipeline', {}).get('name'),
                'user_id': issue_event.get('user_id'),
                'created_at': issue_event.get('created_at')
            }
            singer.write_record('issue_events', record)
            # with singer.metrics.record_counter('issue_events') as counter:
            #     counter.increment()

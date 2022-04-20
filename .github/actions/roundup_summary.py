import json
import os
from datetime import date, timedelta
from typing import Iterable

import requests


ISSUE_ENDPOINT = "https://github.com/python/cpython/issues"
SEARCH_ENDPOINT = "https://api.github.com/search/issues"
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
MAILGUN_ENDPOINT = "https://api.mailgun.net/v3/mg.python.org"


def get_issue_counts(token: str) -> tuple[int, int]:
    """use the GraphQL API to get the number of opened and closed issues
    without having to query every single issue and count them."""
    data = {
        "query": """
        {
            repository(owner: "python", name: "cpython") {
                open: issues(states: OPEN) { totalCount }
                closed: issues(states: CLOSED) { totalCount }
            }
        }
        """
    }
    response = requests.post(GRAPHQL_ENDPOINT, json=data, headers={
        "Authorization": f"Bearer {token}",
        "accept": "application/vnd.github.v3+json"
    })
    repo = response.json()["data"]["repository"]
    open = repo["open"]["totalCount"]
    closed = repo["closed"]["totalCount"]
    return open, closed

def get_issues(filters: Iterable[str], token: str, all_: bool = True):
    """return a list of results from the Github search API"""
    # TODO: if there are more than 100 issues, we need to include pagination
    # this doesn't occur very often, but it should still be included just incase.
    search = " ".join(filters)
    data = {"query": """
        {{
            search(query:"{}" type: ISSUE first: 100)
            {{
                pageInfo {{ hasNextPage endCursor startCursor }}
                nodes {{
                    ... on Issue {{
                        title number author {{ login }} closedAt createdAt
                    }}
                }}
            }}
        }}
    """.format(search)}
    response = requests.post(GRAPHQL_ENDPOINT, json=data, headers={
        "Authorization": f"Bearer {token}",
        "accept": "application/vnd.github.v3+json"
    })
    return response.json()["data"]["search"]["nodes"]

def send_report(report: str, token: str) -> None:
    """send the report using the Mailgun API"""
    # TODO: implement this function, mailgun have a REST API
    # which can be called to send the emails.
    # https://documentation.mailgun.com/en/latest/api-intro.html#introduction
    params = {
        "from": "Cpython Issues <github@mg.python.org>",
        "to": "new-bugs-announce@python.org",
        "subject": "Summary of Python tracker Issues",
        "template": ""
    }

if __name__ == '__main__':
    date_from = date.today() - timedelta(days=7)
    github_token = os.environ.get("github_api_token") or ""
    mailgun_token = os.environ.get("mailgun_api_key") or ""

    num_open, num_closed = get_issue_counts(github_token)
    closed = get_issues(("repo:python/cpython", f"closed:>{date_from}", "type:issue"), github_token)
    opened = get_issues(("repo:python/cpython", "state:open", f"created:>{date_from}", "type:issue"), github_token)
    most_discussed = get_issues(
        ("repo:python/cpython", "state:open", "type:issue", "sort:comments"),
        github_token,
        False)
    no_comments = get_issues(
        ("repo:python/cpython", "state:open", "type:issue", "comments:0", "sort:updated"),
        github_token,
        False)

    # msg = html.format(
    #     timespan=f"{date_from} - {date.today()}",
    #     tracker_name="Python tracker",
    #     tracker_url=ISSUE_ENDPOINT,
    #     num_opened_issues=f"{num_open:,}",
    #     num_closed_issues=f"{num_closed:,}",
    #     num_new_opened_issues=f"{len(opened):+}",
    #     num_new_closed_issues=f"{len(closed):+}",
    #     total=f"{num_open + num_closed:,}",
    #     total_new=f"{len(opened)-len(closed):+}",
    #     patches=0,
    #     opened_issues=create_issue_table(opened),
    #     closed_issues=create_issue_table(closed),
    #     most_discussed=create_issue_table(most_discussed, limit=10),
    #     no_comments=create_issue_table(no_comments, limit=15)
    # )
#!/usr/bin/python

import json
from datetime import date, datetime, timedelta
from functools import partial
from typing import TypedDict

import requests

TEMPLATE_FILE = "template.html"

class User(TypedDict):
    id: str
    site_admin: bool
    login: str

class Label(TypedDict):
    id: int
    url: str
    name: str

class Issue(TypedDict):
    url: str
    id: int
    number: int
    title: str
    user: User
    labels: list[Label]
    state: str
    locked: bool
    assignee: str | None
    assignees: list[str | None]
    milestone: str | None
    comments: int
    created_at: str
    updated_at: str
    closed_at: str | None
    body: str

def get_issues(max_retries: int = 5) -> list[Issue]:
    """return a list of issues from the Github API that were updated since
    the given parameter"""

    ENDPOINT = "https://api.github.com/repos/python/issues-test-demo-20220218/issues"

    # a list of API parameters can be found here
    # https://docs.github.com/en/rest/reference/issues
    params = {
        "per_page": 100, "sort": "created",
        "direction": "desc", "page": 1, "state": "all",
        "filter": "all"
    }
    headers = {"accept": "application/vnd.github.v3+json"}

    response: list[dict[Any, Any]] = []
    while True:
        for _ in range(max_retries):
            resp = requests.get(
                ENDPOINT,
                params=params,
                headers=headers)

            if resp.status_code == 200:
                break
        else:
            raise ValueError("API is not responding, try again later.")

        data = resp.json()
        if not data:
            break
        params["page"] += 1
        response.extend(data)
    return response

def week_beginning() -> date:
    """calculates the datetime YYYY-MM-DDTHH:MM:SSZ
    of the beginning of the current week"""
    today = datetime.now().date() - timedelta(days=28)
    return today # T%H:%M:%SZ

def is_open(issue: Issue) -> bool:
    return issue["state"] == "open"

def opened_after(issue: Issue, start: date) -> bool:
    return datetime\
        .strptime(issue["created_at"], "%Y-%m-%dT%H:%M:%SZ")\
        .date() > start

def most_discussed(issues: list[Issue], top: int = 10) -> list[Issue]:
    """return a list of n open issues sorted by the number of
    comments"""
    return sorted(
        filter(lambda issue: issue["state"] == "open", issues),
        key=lambda issue: issue["comments"])[:top]

def create_issue_table(issues: list[Issue], limit: int | None = None):
    """format issues into a table which can be displayed on the email.
    Note, this table is not actually an HTML table, rather just n number
    of <p> tags."""
    TEMPLATE = '<p>#{id}: {title}<br><a href="{url}">{url}</a> opened by {opener}</p>'

    if limit is None:
        limit = len(issues)

    table: list[str] = []
    for issue in issues[:limit]:
        if issue["user"]["type"] == "Mannequin":
            username = "Mannequin"
        else:
            username = issue["user"]["login"]

        table.append(TEMPLATE.format(
            id=issue["number"],
            title=issue["title"],
            url="https://github.com/python/issues-test-demo-20220218/issues/{}".format(issue["number"]),
            opener=username))
    return '\n'.join(table)

if __name__ == '__main__':
    start = week_beginning()
    is_new = partial(opened_after, start=start)
    with open("test.json") as file:
        issues = json.load(file)

    open_issues = list(filter(is_open, issues))
    closed_issues = list(filter(lambda x : not is_open(x), issues))

    new_open_issues = list(filter(is_new, open_issues))
    new_closed_issues = list(filter(is_new, closed_issues))
    new_issues = new_open_issues + new_closed_issues

    with open(TEMPLATE_FILE) as file:
        html = file.read()

    msg = html.format(
        timespan=f"{start} - {date.today()}",
        tracker_name="Python tracker",
        tracker_url="https://github.com/python/cpython/issues",
        num_opened_issues=len(open_issues),
        num_closed_issues=len(closed_issues),
        num_new_opened_issues=len(new_open_issues),
        num_new_closed_issues=len(new_closed_issues),
        total=len(issues),
        total_new=len(new_issues),
        patches=0,
        opened_issues=create_issue_table(new_open_issues),
        closed_issues=create_issue_table(new_closed_issues),
    )
    with open("out.html", "w") as file:
        file.write(msg)

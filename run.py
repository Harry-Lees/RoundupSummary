#!/usr/bin/python

import json
from datetime import date, datetime, timedelta
from functools import partial
from typing import TypedDict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

TEMPLATE_FILE = "template.html"
DEBUG = True

class User(TypedDict):
    id: str
    site_admin: bool
    login: str
    type: str

class Label(TypedDict):
    id: int
    url: str
    name: str

class Issue(TypedDict):
    """All of the fields that are used in this script, this class doesn't hold a
    full list of all the fields that may be contained within the response, however,
    most of the other ones are URLs that won't be used here. A full list of the returned
    parameters can be found here:
    https://docs.github.com/en/rest/reference/issues#list-issues-assigned-to-the-authenticated-user--code-samples"""
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
    """return a full list of issues from the Github API,
    try up to max_retries times before raising ValueError"""

    ENDPOINT = "https://api.github.com/repos/python/issues-test-demo-20220218/issues"

    # a list of API parameters can be found here
    # https://docs.github.com/en/rest/reference/issues
    params = {
        "per_page": 100, "sort": "created",
        "direction": "desc", "page": 1, "state": "all",
        "filter": "all"
    }
    headers = {"accept": "application/vnd.github.v3+json"}

    response: list[Issue] = []
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

def date_range() -> tuple[date, date]:
    """calculates the date of the beginning of the current week"""
    # for testing, this function has been set to just return the date
    # where there are known test issues.
    # today = datetime.now().date() - timedelta(days=7)
    # return today
    return date(2022, 2, 14), date(2022, 2, 20)

def is_open(issue: Issue) -> bool:
    """return whether the given Issue is open"""
    return issue["state"] == "open"

def opened_between(issue: Issue, start: date, stop: date) -> bool:
    """return whether the given issue was opened between the given
    dates."""
    return stop > datetime\
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

def send_report(recipient: str, report: str, html: str | None = None) -> None:
    TRACKER_NAME = "bugs.python.org"
    email = "{} <status@bugs.python.org>".format(TRACKER_NAME)
    headers = {
        "Subject": f"Summary of {TRACKER_NAME} Issues",
        "To": recipient,
        "From": email,
        "Reply-To": email,
        "MIME-Version": "1.0",
        "X-Roundup-Name": TRACKER_NAME
    }
    if html is None:
        msg = MIMEText(report)
    else:
        msg = MIMEMultipart("alternative")
    for name, content in headers.items():
        msg[name] = content

if __name__ == '__main__':
    start, stop = date_range()
    is_new = partial(opened_between, start=start, stop=stop)
    if DEBUG:
        with open("test.json") as file:
            issues = json.load(file)
    else:
        issues = get_issues()

    open_issues = list(filter(is_open, issues))
    closed_issues = list(filter(lambda x : not is_open(x), issues))

    new_open_issues = list(filter(is_new, open_issues))
    new_closed_issues = list(filter(is_new, closed_issues))
    new_issues = new_open_issues + new_closed_issues

    with open(TEMPLATE_FILE) as file:
        html = file.read()

    msg = html.format(
        timespan=f"{start} - {stop}",
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

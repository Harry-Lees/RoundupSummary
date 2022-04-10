#!/usr/bin/python

import json
import os
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TEMPLATE_FILE = "template.html"
ENDPOINT = "https://github.com/python/cpython/issues"
SEARCH_ENDPOINT = "https://api.github.com/search/issues"
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
DEBUG = False


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
    args = json.dumps(data).encode()
    request = Request(GRAPHQL_ENDPOINT, data=args)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("accept", "application/vnd.github.v3+json")

    with urlopen(request) as response:
        response = json.loads(response.read())
        repo = response["data"]["repository"]
        open = repo["open"]["totalCount"]
        closed = repo["closed"]["totalCount"]
        return open, closed

def get(url: str, params: dict[str, str | int], headers: dict[str, str]):
    """helper function to abstract away some urllib boilerplate"""
    args = urlencode(params)
    request = Request(f"{url}?{args}")
    for key, value in headers.items():
        request.add_header(key, value)
    with urlopen(request) as response:
        return json.loads(response.read())

def get_issues(filters: Iterable[str], token: str):
    """return a list of results from the Github search API"""
    params = {"q": " ".join(filters), "per_page": 100, "page": 0}
    headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"Bearer {token}"}

    responses = []
    while True:
        print("fetching page {}".format(params["page"]))
        data = get(SEARCH_ENDPOINT, params, headers)
        responses.extend(data["items"])
        if len(data["items"]) < 100:
            return responses
        params["page"] += 1

def get_most_discussed(issues, top: int = 10):
    pass

def create_issue_table(issues, limit: int | None = None):
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
            url="{}/{}".format(ENDPOINT, issue["number"]),
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
    date_from = date.today() - timedelta(days=7)
    token = os.environ.get("TOKEN")
    if token is None:
        raise ValueError("token is None, please set TOKEN env variable")

    num_open, num_closed = get_issue_counts(token)
    closed = get_issues(("repo:python/cpython", f"closed:>{date_from}", "type:issue"), token)
    opened = get_issues(("repo:python/cpython", "state:open", f"created:>{date_from}", "type:issue"), token)

    with open(TEMPLATE_FILE) as file:
        html = file.read()

    msg = html.format(
        timespan=f"{date_from} - {date.today()}",
        tracker_name="Python tracker",
        tracker_url=ENDPOINT,
        num_opened_issues=num_open,
        num_closed_issues=num_closed,
        num_new_opened_issues=f"{len(opened):+}",
        num_new_closed_issues=f"{len(closed):+}",
        total=num_open + num_closed,
        total_new=f"{len(opened)-len(closed):+}",
        patches=0,
        opened_issues=create_issue_table(opened),
        closed_issues=create_issue_table(closed),
    )
    with open("out.html", "w") as file:
        file.write(msg)

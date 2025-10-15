"""Jira Worklog CLI (Python)

Implements similar behavior to the provided Java tool. Filters worklogs by EMAIL env and by period.
"""
from __future__ import annotations
import os
import sys
import csv
import base64
import requests
from urllib.parse import quote_plus
from datetime import datetime, date, time, timedelta
from dateutil import parser
import pytz
from typing import Optional, Tuple, List, Dict

# load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional at import-time; installation ensures it's present
    pass

DEFAULT_BASE = "https://subex.atlassian.net"


class IssueTotal:
    def __init__(self, key: str, summary: str, project: str, total_seconds: int):
        self.key = key
        self.summary = summary
        self.project = project
        self.total_seconds = total_seconds

    def hours(self):
        return self.total_seconds / 3600.0

    def days(self):
        return self.hours() / 8.0


def compute_range(period: str, tz: Optional[pytz.timezone] = None) -> Optional[Tuple[datetime, datetime]]:
    if tz is None:
        tz = pytz.timezone(os.environ.get('TZ', 'UTC'))
    today = datetime.now(tz).date()
    if period == 'this':
        naive_start = datetime.combine(today.replace(day=1), time.min)
        last_day = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        naive_end = datetime.combine(last_day, time.max)
        start = tz.localize(naive_start)
        end = tz.localize(naive_end)
        return (start, end)
    if period == 'last':
        first_of_this = today.replace(day=1)
        last_month_last_day = first_of_this - timedelta(days=1)
        naive_start = datetime.combine(last_month_last_day.replace(day=1), time.min)
        naive_end = datetime.combine(last_month_last_day, time.max)
        start = tz.localize(naive_start)
        end = tz.localize(naive_end)
        return (start, end)
    return None


def escape(s: Optional[str]) -> str:
    if s is None:
        return ''
    s = s.replace('"', '""')
    if ',' in s or '"' in s or '\n' in s:
        return f'"{s}"'
    return s


def get_env_or_prompt(name: str, prompt_text: str, hide: bool = False) -> str:
    v = os.environ.get(name)
    if v:
        return v
    try:
        if hide:
            import getpass

            return getpass.getpass(prompt_text)
        else:
            return input(prompt_text)
    except KeyboardInterrupt:
        print()
        sys.exit(1)


def search_issues(base: str, email: str, api_token: str, jql: str) -> List[dict]:
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Basic ' + base64.b64encode(f"{email}:{api_token}".encode('utf-8')).decode('utf-8')
    }
    print("Headers: ", headers)
    all_issues = []
    start_at = 0
    max_results = 50
    while True:
        url = f"{base}/rest/api/3/search/jql?jql={quote_plus(jql)}&fields=project,worklog,summary&startAt={start_at}&maxResults={max_results}"
        print("GET", url)
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code // 100 != 2:
            raise RuntimeError(f"Jira API error: {resp.status_code} - {resp.text}")
        root = resp.json()
        issues = root.get('issues', [])
        if not issues:
            break
        all_issues.extend(issues)
        total = int(root.get('total', len(all_issues)))
        returned = int(root.get('maxResults', max_results))
        start_at += returned
        if start_at >= total:
            break
    return all_issues


def main():
    print("Jira Worklog CLI - generates issue-wise worklog CSV")
    base = input(f"Jira base URL [{DEFAULT_BASE}]: ").strip() or DEFAULT_BASE
    email = get_env_or_prompt('EMAIL', 'Email: ')
    api_token = get_env_or_prompt('API_KEY', 'API token: ', hide=True)
    period = input("Period (this, last, all) [this]: ").strip() or 'this'
    if period not in ('this', 'last', 'all'):
        print("Unknown period. Use this, last or all.")
        sys.exit(1)
    out = input("Output file [worklog-report.xlsx]: ").strip() or 'worklog-report.xlsx'
    csv_mode = out.lower().endswith('.csv')

    if period == 'this':
        jql = "worklogAuthor=currentUser() AND worklogDate>=startOfMonth() AND worklogDate<=endOfMonth()"
    elif period == 'last':
        jql = "worklogAuthor=currentUser() AND worklogDate>=startOfMonth(-1) AND worklogDate<=endOfMonth(-1)"
    else:
        jql = "worklogAuthor=currentUser()"

    print("Fetching issues...")
    # Allow running locally without calling Jira by setting MOCK_JIRA=1
    if os.environ.get('MOCK_JIRA') == '1':
        now_iso = datetime.now(pytz.UTC).isoformat()
        user_email = os.environ.get('EMAIL', email)
        issues = [
            {
                'key': 'PROJ-1',
                'fields': {
                    'summary': 'Fix login bug',
                    'project': {'name': 'Project A'},
                    'worklog': {'worklogs': [
                        {'author': {'emailAddress': user_email}, 'timeSpentSeconds': 3600, 'started': now_iso}
                    ]}
                }
            },
            {
                'key': 'PROJ-2',
                'fields': {
                    'summary': 'Add reporting',
                    'project': {'name': 'Project B'},
                    'worklog': {'worklogs': [
                        {'author': {'emailAddress': user_email}, 'timeSpentSeconds': 7200, 'started': now_iso}
                    ]}
                }
            }
        ]
    else:
        try:
            issues = search_issues(base, email, api_token, jql)
        except Exception as ex:
            print("Failed to call Jira:", ex)
            sys.exit(2)

    rng = compute_range(period, pytz.timezone(os.environ.get('TZ', 'UTC')))

    def period_label(period_str: str) -> str:
        tz = pytz.timezone(os.environ.get('TZ', 'UTC'))
        now = datetime.now(tz).date()
        if period_str == 'this':
            return now.strftime('%B %Y')
        if period_str == 'last':
            last = (now.replace(day=1) - timedelta(days=1))
            return last.strftime('%B %Y')
        return period_str

    friendly_period = period_label(period)

    totals: Dict[str, int] = {}
    summaries: Dict[str, str] = {}
    projects: Dict[str, str] = {}

    for issue in issues:
        key = issue.get('key', 'UNKNOWN')
        summary = issue.get('fields', {}).get('summary', '')
        project = issue.get('fields', {}).get('project', {}).get('name', 'UNKNOWN')
        summaries.setdefault(key, summary)
        projects.setdefault(key, project)
        worklogs = issue.get('fields', {}).get('worklog', {}).get('worklogs', [])
        if not isinstance(worklogs, list):
            continue
        issue_seconds = totals.get(key, 0)
        for wl in worklogs:
            author = wl.get('author', {}).get('emailAddress') or wl.get('author', {}).get('name')
            env_email = os.environ.get('EMAIL')
            if env_email and author and author.lower() != env_email.lower():
                continue
            seconds = int(wl.get('timeSpentSeconds') or 0)
            started = wl.get('started')
            if not started:
                continue
            try:
                odt = parser.isoparse(started)
                if odt.tzinfo is None:
                    odt = odt.replace(tzinfo=pytz.UTC)
                if rng is not None:
                    start, end = rng
                    if odt < start or odt > end:
                        continue
                issue_seconds += seconds
            except Exception:
                continue
        totals[key] = issue_seconds

    list_totals = [IssueTotal(k, summaries.get(k, ''), projects.get(k, ''), v) for k, v in totals.items()]
    if period != 'all':
        list_totals = [it for it in list_totals if it.total_seconds > 0]
    list_totals.sort(key=lambda it: it.hours(), reverse=True)

    grand = sum(it.total_seconds for it in list_totals)

    if csv_mode:
        with open(out, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Issue Key', 'Summary', 'Project', 'Total Hours', 'Total Days (8h)'])
            for it in list_totals:
                w.writerow([it.key, it.summary, it.project, f"{it.hours():.2f}", f"{it.days():.2f}"])
            w.writerow(['GRAND TOTAL', '', '', f"{grand/3600.0:.2f}", f"{(grand/3600.0)/8.0:.2f}"])
        print(f"Wrote CSV report to {out}")
    else:
        # produce an Excel .xlsx workbook using openpyxl
        try:
            from openpyxl import Workbook
            from openpyxl.utils import get_column_letter
        except Exception:
            print("openpyxl is required to write Excel files. Install with 'pip install openpyxl'.")
            sys.exit(3)

        wb = Workbook()
        ws = wb.active
        ws.title = 'Worklog'

        # Header rows
        ws.append(['Jira Worklog Report'])
        ws.append([f'Period: {friendly_period}', f'Generated: {datetime.now().isoformat()}'])
        ws.append([])
        headers = ['Issue Key', 'Summary', 'Project', 'Total Hours', 'Total Days (8h)']
        ws.append(headers)

        for it in list_totals:
            ws.append([it.key, it.summary, it.project, float(f"{it.hours():.2f}"), float(f"{it.days():.2f}")])

        # Grand total row
        ws.append(['GRAND TOTAL', '', '', float(f"{grand/3600.0:.2f}"), float(f"{(grand/3600.0)/8.0:.2f}")])

        # simple column width adjustments
        col_widths = {}
        for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
            for i, cell in enumerate(row, start=1):
                val = cell.value
                if val is None:
                    length = 0
                else:
                    length = len(str(val))
                col_widths[i] = max(col_widths.get(i, 0), length)

        for i, width in col_widths.items():
            ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 8), 60)

        # number formatting for hours/days columns
        for row in ws.iter_rows(min_row=5, min_col=4, max_col=5, max_row=ws.max_row):
            for cell in row:
                cell.number_format = '0.00'

        wb.save(out)
        print(f"Wrote Excel report to {out}")


if __name__ == '__main__':
    main()

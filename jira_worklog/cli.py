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
    out = input("Output file [worklog-report.html]: ").strip() or 'worklog-report.html'
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
        def hescape(s: str) -> str:
            return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))

        rows_html: List[str] = []
        for it in list_totals:
            rows_html.append(
                f"<tr><td>{hescape(it.key)}</td><td>{hescape(it.summary)}</td><td>{hescape(it.project)}</td>"
                f"<td style=\"text-align:right\">{it.hours():.2f}</td><td style=\"text-align:right\">{it.days():.2f}</td></tr>"
            )

    friendly_period_escaped = hescape(friendly_period)
    generated = datetime.now().isoformat()
    rows_joined = ''.join(rows_html)
    grand_hours = f"{grand/3600.0:.2f}"
    grand_days = f"{(grand/3600.0)/8.0:.2f}"

    html_template = '''<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Jira Worklog Report</title>
    <style>
        body { font-family: Arial, Helvetica, sans-serif; margin: 24px; }
        table { border-collapse: collapse; width: 100%; max-width: 1200px; }
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { background: #f4f4f6; text-align: left; cursor: pointer; user-select: none; }
        th .sort-indicator { margin-left: 6px; color: #666; font-size: 0.9em; }
        tr:nth-child(even) { background: #fafafa; }
        tr:hover { background: #f1f7ff; }
        .right { text-align: right; }
        .grand { font-weight: 700; background: #eef6ff; }
    </style>
</head>
<body>
    <h1>Jira Worklog Report</h1>
        <p>Period: __FRIENDLY_PERIOD__ &nbsp;|&nbsp; Generated: __GENERATED__</p>
    <table id="report-table">
        <thead>
            <tr>
                <th data-col="0" data-type="string">Issue Key<span class="sort-indicator"></span></th>
                <th data-col="1" data-type="string">Summary<span class="sort-indicator"></span></th>
                <th data-col="2" data-type="string">Project<span class="sort-indicator"></span></th>
                <th data-col="3" data-type="number">Total Hours<span class="sort-indicator"></span></th>
                <th data-col="4" data-type="number">Total Days (8h)<span class="sort-indicator"></span></th>
            </tr>
        </thead>
        <tbody>
            __ROWS__
            <tr class="grand"><td>GRAND TOTAL</td><td></td><td></td><td style="text-align:right">__GRAND_HOURS__</td><td style="text-align:right">__GRAND_DAYS__</td></tr>
        </tbody>
    </table>

    <script>
        (function(){
            const table = document.getElementById('report-table');
            if (!table) return;
            const tbody = table.tBodies[0];
            const headers = table.tHead.rows[0].cells;

            function getCellValue(row, idx){
                const c = row.cells[idx];
                if (!c) return '';
                return c.textContent.trim();
            }

            function parseValue(val, type){
                if (type === 'number'){
                    const n = parseFloat(val.replace(/,/g,''));
                    return isNaN(n) ? -Infinity : n;
                }
                return val.toLowerCase();
            }

            function clearIndicators(){
                Array.from(headers).forEach(h => {
                    const span = h.querySelector('.sort-indicator');
                    if (span) span.textContent = '';
                });
            }

            Array.from(headers).forEach((th, idx) => {
                th.style.cursor = 'pointer';
                th.addEventListener('click', function(){
                    const type = th.getAttribute('data-type') || 'string';
                    const current = th.getAttribute('data-order') || 'desc';
                    const newOrder = current === 'asc' ? 'desc' : 'asc';
                    th.setAttribute('data-order', newOrder);
                    Array.from(headers).forEach(h => { if (h !== th) h.removeAttribute('data-order'); });

                    const rows = Array.from(tbody.rows).filter(r => !r.classList.contains('grand'));
                    rows.sort((a,b) => {
                        const va = parseValue(getCellValue(a, idx), type);
                        const vb = parseValue(getCellValue(b, idx), type);
                        if (va < vb) return newOrder === 'asc' ? -1 : 1;
                        if (va > vb) return newOrder === 'asc' ? 1 : -1;
                        return 0;
                    });

                    rows.forEach(r => tbody.appendChild(r));
                    const grandRow = tbody.querySelector('tr.grand');
                    if (grandRow) tbody.appendChild(grandRow);

                    clearIndicators();
                    const indicator = th.querySelector('.sort-indicator');
                    if (indicator) indicator.textContent = newOrder === 'asc' ? '▲' : '▼';
                });
            });
        })();
    </script>
</body>
</html>
'''

    html = (html_template
        .replace('__FRIENDLY_PERIOD__', friendly_period_escaped)
        .replace('__GENERATED__', generated)
        .replace('__ROWS__', rows_joined)
        .replace('__GRAND_HOURS__', grand_hours)
        .replace('__GRAND_DAYS__', grand_days))

    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Wrote HTML report to {out}")


if __name__ == '__main__':
    main()

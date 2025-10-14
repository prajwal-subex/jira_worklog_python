Jira Worklog Python

This CLI replicates the Java tool behavior: fetches issues for the current user and produces an issue-wise CSV of total worklog hours/days. It applies two specific requirements:

- Filters worklogs by the EMAIL environment variable (only worklogs authored by that email are counted).
- Filters worklogs by the selected period, making sure the worklog `started` timestamp falls within the period (taking timezone into account).

Usage:

- Set EMAIL and API_KEY environment variables (or enter when prompted).
- Run: python -m jira_worklog.cli

Files:
- `jira_worklog/cli.py` - main CLI
- `requirements.txt` - dependencies
- `tests/test_range.py` - basic unit tests

Notes:
- This tool uses the Jira Cloud REST API v3.
- The script performs client-side filtering by parsing the `started` field returned in worklogs and comparing it to the period range.
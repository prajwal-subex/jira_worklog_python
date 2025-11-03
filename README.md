Jira Worklog Python

This CLI replicates the Java tool behavior: it fetches issues for the current user and produces a worklog report. The tool now writes an Excel (.xlsx) report by default and keeps a CSV fallback if you request a .csv output filename.

Key behaviors
- Filters worklogs by the EMAIL environment variable (only worklogs authored by that email are counted).
- Filters worklogs by the selected period, making sure the worklog `started` timestamp falls within the period (timezone-aware).

Output
- Excel (default): when the output filename does not end with .csv the CLI writes an .xlsx file using openpyxl. The workbook includes these sheets:
	- `Worklog` — issue-wise totals (Issue Key, Summary, Project, Total Hours, Total Days (8h)).
	- `Details` — per-worklog rows with Started (IST), Created (IST), Hours and Comment.
	- `By Day` — per-date, per-issue rows showing Date (IST), Issue Key, Project, Hours and a merged `Day Total` column that sums the hours for that date. Date and Day Total cells are merged across rows for the same date for compact presentation.
- CSV fallback: if you pass a filename ending with .csv the CLI writes a simple CSV with Issue Key, Summary, Project, Total Hours, Total Days.

Usage
1. Create a `.env` file in the project root with your Jira credentials:
   ```
   EMAIL=your.email@subex.com
   API_KEY=your_jira_api_token_here
   ```
   Note: You can generate an API token from your Atlassian account settings (https://id.atlassian.com/manage-profile/security/api-tokens)

2. Run the CLI:
   ```
   python -m jira_worklog.cli
   ```
   The script will:
   - Read credentials from `.env` file (or prompt if not found)
   - Use default Jira URL (https://subex.atlassian.net)
   - Default to current month's worklogs
   - Generate report as `worklog-report.xlsx` (or specify another filename when prompted)

Local testing helper
- To run the CLI without calling Jira, set environment variable `MOCK_JIRA=1` before running; this generates sample data and writes the report locally.

Dependencies
- The project depends on the packages listed in `requirements.txt`. Excel output requires `openpyxl` to be installed (the README's requirements file includes it).

Files
- `jira_worklog/cli.py` - main CLI
- `requirements.txt` - dependencies (ensure `openpyxl` is installed for Excel output)
- `tests/test_range.py` - basic unit tests

Notes
- The script uses the Jira Cloud REST API v3 and performs client-side filtering by parsing worklog timestamps. All timestamps in Excel are converted/shown in IST (UTC+5:30).

Setup (recommended)
- On Windows PowerShell create and use a local virtual environment named `.venv` (the included `run_report.bat` expects this location and will prefer the venv's Python if present):

	```powershell
	# create a venv in the project root
	python -m venv .venv

	# activate it for this session
	& .\.venv\Scripts\Activate.ps1

	# upgrade pip and install project dependencies
	python -m pip install --upgrade pip
	pip install -r .\requirements.txt

	# run the CLI (or double-click run_report.bat)
	python -m jira_worklog.cli
	```

If you do not create `.venv`, `run_report.bat` will run the `python` available on your PATH as a fallback — make sure that Python has the required dependencies installed.
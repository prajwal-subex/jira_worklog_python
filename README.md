# Jira Worklog Python CLI

A command-line tool to fetch and report Jira worklogs for the current user, with output in Excel or CSV format.

---

## Features
- **Filters worklogs** by your email (set in `.env` as `EMAIL`).
- **Period selection**: choose current month, last month, or all time.
- **Excel output** (default):
  - `Worklog` sheet: issue-wise totals (Key, Summary, Project, Hours, Days)
  - `Details` sheet: per-worklog entries (Started, Created, Hours, Comment)
  - `By Day` sheet: date-wise, per-issue hours with daily totals
- **CSV output**: simple summary if you specify a `.csv` filename
- **Timezone**: All timestamps in Excel are shown in IST (UTC+5:30)

---

## Quick Start

### 1. Prerequisites
- Python 3.8+
- [Jira API token](https://id.atlassian.com/manage-profile/security/api-tokens)
- Your Jira email address

### 2. Setup

#### a. Clone and install dependencies
```powershell
# Clone the repo and enter the directory
git clone https://github.com/yourusername/jira-worklog-python-cli.git
cd jira-worklog-python-cli

# (Recommended) Create and activate a virtual environment
python -m venv .venv
& .\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### b. Configure credentials
Create a `.env` file in the project root:
```ini
EMAIL=your.email@subex.com
API_KEY=your_jira_api_token_here
```

### 3. Run the CLI
```powershell
python -m jira_worklog.cli
```
- The script will use your `.env` file for credentials.
- Default Jira URL: `https://subex.atlassian.net`
- Default period: current month
- Default output: `worklog-report.xlsx` (Excel)

You can change the period or output filename when prompted.

---

## Usage Details

- **Worklog filtering**: Only worklogs authored by your `EMAIL` are included.
- **Period options**:
  - `this`: Current month (default)
  - `last`: Previous month
  - `all`: All available worklogs
- **Output**:
  - Excel (`.xlsx`): full report with summary, details, and by-day sheets
  - CSV (`.csv`): summary only

---

## Local Testing (No Jira Calls)
To generate a sample report without calling Jira:
```powershell
$env:MOCK_JIRA=1
python -m jira_worklog.cli
```

---

## Windows: Using the Batch File
- The repository includes a `run_report.bat` file for convenience on Windows.
- Double-click `run_report.bat` or run it from a command prompt to launch the CLI with the correct environment (it will use the `.venv` if present, or fall back to your system Python).
- This is the easiest way for non-technical users to generate the report without typing commands.

---

## File Structure
- `jira_worklog/cli.py` — main CLI script
- `requirements.txt` — dependencies
- `tests/test_range.py` — unit tests
- `run_report.bat` — Windows batch file to launch the CLI

---

## Notes
- Uses Jira Cloud REST API v3
- All Excel timestamps are in IST (UTC+5:30)
- If `.env` is missing, you will be prompted for credentials
- For Excel output, `openpyxl` must be installed (included in requirements)

---

## Troubleshooting
- If you see authentication errors, check your `.env` file and API token
- If Excel output fails, ensure `openpyxl` is installed
- For large worklogs, the tool paginates and optimizes API calls
- Make sure that existing Excel file is not open while generating the new one.

---

## Example `.env` file
```ini
EMAIL=your.email@subex.com
API_KEY=your_jira_api_token_here
```

---

## License
MIT
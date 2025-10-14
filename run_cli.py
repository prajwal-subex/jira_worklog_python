# Small launcher for double-click execution
import os
import sys
from jira_worklog import cli

if __name__ == '__main__':
    # ensure current directory is project root so .env and files are found
    os.chdir(os.path.dirname(__file__))
    try:
        cli.main()
    except Exception as e:
        print('Error running CLI:', e)
        input('Press Enter to exit...')
        sys.exit(1)

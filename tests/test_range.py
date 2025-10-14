from jira_worklog.cli import compute_range
import pytz
from datetime import datetime, time


def test_this_month_range():
    tz = pytz.timezone('UTC')
    start, end = compute_range('this', tz)
    assert start.tzinfo is not None
    assert end.tzinfo is not None
    assert start.day == 1
    assert start.hour == 0
    assert end.hour == 23


def test_last_month_range():
    tz = pytz.timezone('UTC')
    start, end = compute_range('last', tz)
    assert start.tzinfo is not None
    assert end.tzinfo is not None
    assert start.day == 1
    assert start.hour == 0
    assert end.hour == 23


def test_all_range():
    r = compute_range('all', pytz.timezone('UTC'))
    assert r is None

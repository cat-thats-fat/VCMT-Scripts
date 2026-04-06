#!/usr/bin/env python3
"""Tests for enriched diagnostics and HTML reporting."""

from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from jane_shift_checker import (
    ScheduleReader,
    ShiftChecker,
    ShiftTimeBlock,
    ScheduledShift,
    JaneShift,
    DateRangeResults,
    generate_html_report,
)


def test_exclusion_diagnostics():
    reader = ScheduleReader('janechecks26.xlsx')
    _ = reader.get_shifts_for_date(datetime(2026, 6, 12))
    diag = reader.last_exclusion_counts
    assert 'ns' in diag and 'on_call' in diag and 'outreach' in diag
    assert diag['ns'] > 0
    assert diag['on_call'] > 0
    assert diag['outreach'] > 0


def test_nearest_candidate_diagnostics():
    checker = ShiftChecker('janechecks26.xlsx', 'staff.json')
    tz = timezone(timedelta(hours=-7))

    scheduled = ScheduledShift(
        date=datetime(2026, 7, 20),
        staff_name='Test User',
        shift_code='PM3-1',
        location='VCMT Clinic: The Mend',
        hours=4.5,
        day_of_week='mon',
        time_blocks=[ShiftTimeBlock('16:00', '20:30')],
    )

    # Deliberate offset so nearest candidate is captured but no full match.
    jane = JaneShift(
        id=123,
        start_at=datetime(2026, 7, 20, 15, 30, tzinfo=tz),
        end_at=datetime(2026, 7, 20, 21, 0, tzinfo=tz),
        staff_member_id=1,
        location_id=1,
        notes=None,
        tags=[],
    )

    res = checker._validate_time_blocks(scheduled, [jane], time_tolerance_minutes=15)
    assert not res['fully_matched']
    assert len(res['nearest_candidates']) == 1
    nearest = res['nearest_candidates'][0]
    assert nearest['start_diff_minutes'] > 0
    assert nearest['end_diff_minutes'] > 0


def test_html_report_contains_details():
    out = Path('/tmp/jane_report_test.html')
    day = {
        'date': '2026-07-20',
        'day_of_week': 'Monday',
        'scheduled_shifts': 2,
        'jane_shifts': 2,
        'matched_shifts': [],
        'missing_in_jane': [
            {
                'staff_name': 'Calvin Mandap',
                'shift_code': 'PM3-1',
                'expected_time_blocks': [('16:00', '20:30')],
                'validation_issues': ['Missing 1 expected time blocks'],
                'nearest_jane_shift': {'id': 1, 'start': '2026-07-20T15:30:00-07:00', 'end': '2026-07-20T21:00:00-07:00'},
                'start_diff_minutes': 30,
                'end_diff_minutes': 30,
                'reason_code': 'time_offset',
                'reason_detail': 'Nearest shift is offset',
            }
        ],
        'extra_in_jane': [
            {
                'staff_name': 'Calvin Mandap',
                'jane_shift_id': 1,
                'start': '2026-07-20T15:30:00-07:00',
                'end': '2026-07-20T21:00:00-07:00',
                'tags': [],
                'notes': 'PM3-1',
                'reason_code': 'unexpected_extra_shift',
                'reason_detail': 'No expected match',
            }
        ],
        'name_matching_issues': [],
        'parse_diagnostics': {'raw_records': 2, 'accepted': 2},
        'exclusion_diagnostics': {'blank_or_stat': 0, 'ns': 0, 'on_call': 0, 'outreach': 0},
    }

    results = DateRangeResults(
        start_date=date(2026, 7, 20),
        end_date=date(2026, 7, 20),
        total_days=1,
        processed_days=1,
        daily_results=[day],
        summary={
            'total_scheduled_shifts': 2,
            'total_jane_shifts': 2,
            'total_matched_shifts': 0,
            'total_missing_in_jane': 1,
            'total_extra_in_jane': 1,
            'total_name_matching_issues': 0,
            'days_processed': 1,
            'days_with_issues': 1,
            'total_excluded_blank_or_stat': 0,
            'total_excluded_ns': 0,
            'total_excluded_on_call': 0,
            'total_excluded_outreach': 0,
            'total_parse_raw_records': 2,
            'total_parse_accepted': 2,
            'total_parse_skipped_missing_required': 0,
            'total_parse_skipped_missing_staff': 0,
            'total_parse_skipped_break': 0,
            'total_parse_skipped_patient': 0,
            'total_parse_skipped_parse_error': 0,
        },
    )

    generate_html_report(results, str(out))
    html = out.read_text()
    assert 'Missing In Jane' in html
    assert 'Extra In Jane' in html
    assert 'Calvin Mandap' in html
    assert 'time_offset' in html


def main():
    test_exclusion_diagnostics()
    test_nearest_candidate_diagnostics()
    test_html_report_contains_details()
    print('All reporting quality checks passed.')


if __name__ == '__main__':
    main()

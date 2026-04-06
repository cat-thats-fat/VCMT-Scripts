#!/usr/bin/env python3
"""
Focused parser and time-block validation checks.
"""

from datetime import datetime, timedelta, timezone
from jane_shift_checker import (
    JaneAppClient,
    ShiftChecker,
    ScheduledShift,
    ShiftTimeBlock,
    JaneShift,
)


def run_parser_checks():
    print("Testing Jane API parser behavior...")
    client = JaneAppClient()

    payload = {
        "appointments": [
            {
                "id": 1,
                "start_at": "2026-05-04T08:30:00-07:00",
                "end_at": "2026-05-04T15:30:00-07:00",
                "staff_member_id": 100,
                "break": True,
            },
            {
                "id": 2,
                "start_at": "2026-05-04T09:00:00-07:00",
                "end_at": "2026-05-04T10:00:00-07:00",
                "staff_member_id": 200,
                "patient_id": 999,
            },
            {
                "id": 3,
                "start_at": "2026-05-04T11:00:00-07:00",
                "staff_member_id": 200,
            },
        ],
        "shifts": [
            {
                "id": 10,
                "start_at": "2026-05-04T08:00:00-07:00",
                "end_at": "2026-05-04T15:30:00-07:00",
                "staff_member_id": 123,
                "notes_text": "AM4-1",
                "tags": [{"name": "Student"}],
            },
            {
                "id": 11,
                "start_at": "2026-05-04T15:30:00-07:00",
                "end_at": "2026-05-04T21:00:00-07:00",
                "staff_member_id": 124,
                "state": "scheduled",
            },
        ],
    }

    shifts, stats = client._parse_calendar_payload(payload)

    assert len(shifts) == 2, f"Expected 2 accepted shifts, got {len(shifts)}"
    assert stats["raw_records"] == 5
    assert stats["accepted"] == 2
    assert stats["skipped_break"] == 1
    assert stats["skipped_patient"] == 1
    assert stats["skipped_missing_required"] == 1

    print("  ✅ includes real shifts, excludes breaks/patients/malformed")


def run_time_validation_checks():
    print("Testing time-block validation behavior...")
    checker = ShiftChecker("janechecks26.xlsx", "staff.json")

    base_date = datetime(2026, 5, 4)
    tz = timezone(timedelta(hours=-7))

    # Exact + within tolerance
    scheduled = ScheduledShift(
        date=base_date,
        staff_name="Test User",
        shift_code="TEST",
        location="Test",
        hours=7.5,
        day_of_week="mon",
        time_blocks=[ShiftTimeBlock("08:00", "12:00")],
    )

    jane_exact = JaneShift(
        id=1,
        start_at=datetime(2026, 5, 4, 8, 0, tzinfo=tz),
        end_at=datetime(2026, 5, 4, 12, 0, tzinfo=tz),
        staff_member_id=1,
        location_id=1,
        notes=None,
        tags=[],
    )
    result_exact = checker._validate_time_blocks(scheduled, [jane_exact], time_tolerance_minutes=15)
    assert result_exact["fully_matched"]

    jane_within = JaneShift(
        id=2,
        start_at=datetime(2026, 5, 4, 8, 10, tzinfo=tz),
        end_at=datetime(2026, 5, 4, 12, 10, tzinfo=tz),
        staff_member_id=1,
        location_id=1,
        notes=None,
        tags=[],
    )
    result_within = checker._validate_time_blocks(scheduled, [jane_within], time_tolerance_minutes=15)
    assert result_within["fully_matched"]

    jane_outside = JaneShift(
        id=3,
        start_at=datetime(2026, 5, 4, 8, 20, tzinfo=tz),
        end_at=datetime(2026, 5, 4, 12, 20, tzinfo=tz),
        staff_member_id=1,
        location_id=1,
        notes=None,
        tags=[],
    )
    result_outside = checker._validate_time_blocks(scheduled, [jane_outside], time_tolerance_minutes=15)
    assert not result_outside["fully_matched"]

    # Split shift
    scheduled_split = ScheduledShift(
        date=base_date,
        staff_name="Test User",
        shift_code="SPLIT",
        location="Test",
        hours=7.0,
        day_of_week="mon",
        time_blocks=[ShiftTimeBlock("08:30", "12:00"), ShiftTimeBlock("13:00", "16:30")],
    )

    split_shifts = [
        JaneShift(
            id=4,
            start_at=datetime(2026, 5, 4, 8, 30, tzinfo=tz),
            end_at=datetime(2026, 5, 4, 12, 0, tzinfo=tz),
            staff_member_id=1,
            location_id=1,
            notes=None,
            tags=[],
        ),
        JaneShift(
            id=5,
            start_at=datetime(2026, 5, 4, 13, 0, tzinfo=tz),
            end_at=datetime(2026, 5, 4, 16, 30, tzinfo=tz),
            staff_member_id=1,
            location_id=1,
            notes=None,
            tags=[],
        ),
    ]

    result_split = checker._validate_time_blocks(scheduled_split, split_shifts, time_tolerance_minutes=15)
    assert result_split["fully_matched"]

    # AM4-style: one expected block in legend, but two Jane segments with lunch gap.
    scheduled_am4 = ScheduledShift(
        date=base_date,
        staff_name="Test User",
        shift_code="AM4-1",
        location="Test",
        hours=6.5,
        day_of_week="mon",
        time_blocks=[ShiftTimeBlock("08:30", "15:00")],
    )
    am4_segments = [
        JaneShift(
            id=6,
            start_at=datetime(2026, 5, 4, 8, 30, tzinfo=tz),
            end_at=datetime(2026, 5, 4, 11, 30, tzinfo=tz),
            staff_member_id=1,
            location_id=1,
            notes=None,
            tags=[],
        ),
        JaneShift(
            id=7,
            start_at=datetime(2026, 5, 4, 12, 0, tzinfo=tz),
            end_at=datetime(2026, 5, 4, 15, 0, tzinfo=tz),
            staff_member_id=1,
            location_id=1,
            notes=None,
            tags=[],
        ),
    ]
    result_am4 = checker._validate_time_blocks(scheduled_am4, am4_segments, time_tolerance_minutes=15)
    assert result_am4["fully_matched"]
    assert result_am4["matched_blocks"][0]["match_type"] == "split_shift"

    print("  ✅ exact/within/outside/split scenarios behave as expected")


def main():
    run_parser_checks()
    run_time_validation_checks()
    print("All parser/time validation checks passed.")


if __name__ == "__main__":
    main()

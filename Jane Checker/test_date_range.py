#!/usr/bin/env python3
"""
Test the date range functionality
"""

from jane_shift_checker import ShiftChecker, DateRangeManager
from datetime import date, datetime

def test_date_range_functionality():
    """Test the date range functionality without API calls"""
    print("Testing Date Range Functionality")
    print("=" * 50)
    
    # Test DateRangeManager
    start_date = date(2026, 5, 12)  # Monday
    end_date = date(2026, 5, 18)    # Sunday
    
    print("Testing DateRangeManager...")
    
    # Test without Sundays
    manager = DateRangeManager(start_date, end_date, include_sundays=False)
    working_dates = manager.get_working_dates()
    
    print(f"Date range: {start_date} to {end_date}")
    print(f"Working dates (excluding Sundays): {len(working_dates)} days")
    for d in working_dates:
        print(f"  - {d.strftime('%Y-%m-%d (%A)')}")
    
    # Test with Sundays
    manager_with_sundays = DateRangeManager(start_date, end_date, include_sundays=True)
    all_dates = manager_with_sundays.get_working_dates()
    
    print(f"\\nAll dates (including Sundays): {len(all_dates)} days")
    for d in all_dates:
        print(f"  - {d.strftime('%Y-%m-%d (%A)')}")
    
    print()
    
    # Test ShiftChecker with small date range (without API calls)
    print("Testing ShiftChecker date range (Excel only)...")
    checker = ShiftChecker('janechecks26.xlsx', 'staff.json')
    
    # Test a 3-day range
    test_start = date(2026, 5, 12)  # Monday
    test_end = date(2026, 5, 14)    # Wednesday
    
    print(f"Checking shifts from {test_start} to {test_end} (Excel only)...")
    
    # Simulate the date range check without JaneApp API
    date_manager = DateRangeManager(test_start, test_end, include_sundays=False)
    working_dates = date_manager.get_working_dates()
    
    total_shifts_found = 0
    total_staff_matched = 0
    
    for i, current_date in enumerate(working_dates):
        print(f"\\nProcessing day {i + 1}/{len(working_dates)}: {current_date.strftime('%Y-%m-%d (%A)')}")
        
        # Convert to datetime for existing methods
        check_datetime = datetime.combine(current_date, datetime.min.time())
        scheduled_shifts = checker.schedule_reader.get_shifts_for_date(check_datetime)
        
        print(f"  Found {len(scheduled_shifts)} scheduled shifts")
        
        # Test staff matching
        matched_count = 0
        for shift in scheduled_shifts:
            staff_match = checker.staff_matcher.find_staff_match(shift.staff_name, checker.staff_members)
            if staff_match:
                matched_count += 1
        
        print(f"  Staff matched: {matched_count}/{len(scheduled_shifts)}")
        
        # Show sample shifts with time blocks
        if scheduled_shifts:
            print("  Sample shifts with time blocks:")
            for shift in scheduled_shifts[:3]:
                time_blocks_str = []
                for block in shift.time_blocks:
                    time_blocks_str.append(f"{block.start_time}-{block.end_time}")
                time_info = " + ".join(time_blocks_str) if time_blocks_str else "No times"
                print(f"    - {shift.staff_name}: {shift.shift_code} ({time_info})")
        
        total_shifts_found += len(scheduled_shifts)
        total_staff_matched += matched_count
    
    print(f"\\n📊 RANGE SUMMARY:")
    print(f"  Total days processed: {len(working_dates)}")
    print(f"  Total shifts found: {total_shifts_found}")
    print(f"  Total staff matched: {total_staff_matched}")
    print(f"  Match rate: {total_staff_matched/total_shifts_found*100:.1f}%" if total_shifts_found > 0 else "  Match rate: N/A")

def test_command_line_parsing():
    """Test that the command line interface works"""
    print("\\n" + "=" * 50)
    print("Testing Command Line Interface")
    print("=" * 50)
    
    print("Available command examples:")
    print()
    
    print("Single date check:")
    print("  python jane_shift_checker.py --date 2026-05-12")
    print()
    
    print("Date range check:")
    print("  python jane_shift_checker.py --start-date 2026-05-12 --end-date 2026-05-18")
    print()
    
    print("Date range with Sundays:")
    print("  python jane_shift_checker.py --start-date 2026-05-12 --end-date 2026-05-18 --include-sundays")
    print()
    
    print("With JaneApp API:")
    print("  python jane_shift_checker.py --start-date 2026-05-12 --end-date 2026-05-18 --cookies 'your_cookies'")
    print()
    
    print("Generate HTML report:")
    print("  python jane_shift_checker.py --start-date 2026-05-12 --end-date 2026-05-18 --report-file report.html")
    print()
    
    print("JSON output:")
    print("  python jane_shift_checker.py --start-date 2026-05-12 --end-date 2026-05-18 --output json")

if __name__ == "__main__":
    test_date_range_functionality()
    test_command_line_parsing()
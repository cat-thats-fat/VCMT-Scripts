#!/usr/bin/env python3
"""
Example usage of the JaneApp shift checker
"""

from jane_shift_checker import ShiftChecker
from datetime import datetime
import json

def example_check():
    """Example of checking shifts for a specific date"""
    print("JaneApp Shift Checker - Example Usage")
    print("=" * 50)
    
    # Initialize the checker
    checker = ShiftChecker('janechecks26.xlsx', 'staff.json')
    
    # Check a specific date (you can change this)
    check_date = datetime(2026, 5, 12)  # Monday, May 12, 2026
    
    print(f"Checking shifts for {check_date.strftime('%A, %B %d, %Y')}")
    
    # Perform the check (without JaneApp API - just Excel analysis)
    results = {
        'date': check_date.strftime('%Y-%m-%d'),
        'scheduled_shifts': 0,
        'jane_shifts': 0,  # Would be populated with real API call
        'missing_in_jane': [],
        'extra_in_jane': [],
        'name_matching_issues': [],
        'matched_shifts': []
    }
    
    # Get scheduled shifts from Excel
    scheduled_shifts = checker.schedule_reader.get_shifts_for_date(check_date)
    results['scheduled_shifts'] = len(scheduled_shifts)
    
    print(f"Found {len(scheduled_shifts)} scheduled shifts in Excel")
    
    # Analyze staff matching
    matched = 0
    unmatched = 0
    unmatched_details = []
    
    for shift in scheduled_shifts:
        staff_match = checker.staff_matcher.find_staff_match(shift.staff_name, checker.staff_members)
        
        if staff_match:
            matched += 1
            # This would be a matched shift if we had Jane data
            results['matched_shifts'].append({
                'staff_name': staff_match.professional_name,
                'excel_shift': shift.shift_code,
                'excel_name': shift.staff_name
            })
        else:
            unmatched += 1
            unmatched_details.append({
                'staff_name': shift.staff_name,
                'shift_code': shift.shift_code,
                'message': 'No matching staff member found in JaneApp'
            })
    
    results['name_matching_issues'] = unmatched_details
    
    print(f"Staff matching results:")
    print(f"  - Matched: {matched}")
    print(f"  - Unmatched: {unmatched}")
    
    # Show sample matched shifts
    if results['matched_shifts']:
        print(f"\nSample matched shifts:")
        for shift in results['matched_shifts'][:5]:
            print(f"  - {shift['staff_name']}: {shift['excel_shift']}")
    
    # Show unmatched staff
    if unmatched_details:
        print(f"\nStaff needing manual mapping:")
        for issue in unmatched_details[:10]:
            print(f"  - {issue['staff_name']}: {issue['shift_code']}")
        
        if len(unmatched_details) > 10:
            print(f"  ... and {len(unmatched_details) - 10} more")
    
    print(f"\n" + "="*50)
    print("NEXT STEPS:")
    print("1. Create staff mappings using: python create_mappings.py")
    print("2. Edit staff_mappings.json with manual mappings")
    print("3. Test with JaneApp API using browser cookies")
    print("4. Run: python jane_shift_checker.py --date 2026-05-12 --cookies 'your_cookies'")
    
    return results

if __name__ == "__main__":
    example_check()
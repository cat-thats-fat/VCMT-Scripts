#!/usr/bin/env python3
"""
Test script for the JaneApp shift checker
"""

import sys
from datetime import datetime
from jane_shift_checker import ShiftChecker

def test_basic_functionality():
    """Test basic functionality without JaneApp API calls"""
    print("Testing JaneApp Shift Checker...")
    
    try:
        # Initialize checker
        checker = ShiftChecker('janechecks26.xlsx', 'staff.json')
        print(f"✅ Successfully loaded {len(checker.staff_members)} staff members")
        
        # Test schedule reading for a date (May 12, 2026 - Monday)
        test_date = datetime(2026, 5, 12)
        scheduled_shifts = checker.schedule_reader.get_shifts_for_date(test_date)
        print(f"✅ Found {len(scheduled_shifts)} scheduled shifts for {test_date.strftime('%Y-%m-%d')}")
        
        # Show sample shifts
        if scheduled_shifts:
            print("\nSample scheduled shifts:")
            for shift in scheduled_shifts[:5]:
                staff_match = checker.staff_matcher.find_staff_match(shift.staff_name, checker.staff_members)
                match_status = f"→ JaneApp: {staff_match.professional_name}" if staff_match else "→ UNMATCHED"
                print(f"  - Excel: {shift.staff_name} {match_status} → Shift: {shift.shift_code}")
        
        # Test legend lookup
        if checker.schedule_reader.legend is not None and not checker.schedule_reader.legend.empty:
            print(f"✅ Legend loaded with {len(checker.schedule_reader.legend)} shift types")
            print("\nSample shift types:")
            for _, row in checker.schedule_reader.legend.head(5).iterrows():
                print(f"  - {row.get('Tile', 'N/A')}: {row.get('Hours', 0)} hours at {row.get('Location', 'Unknown')}")
        
        # Test staff matching
        unmatched_count = 0
        matched_count = 0
        
        for shift in scheduled_shifts:
            staff_match = checker.staff_matcher.find_staff_match(shift.staff_name, checker.staff_members)
            if staff_match:
                matched_count += 1
            else:
                unmatched_count += 1
        
        print(f"\n📊 Staff Matching Results:")
        print(f"  - Matched: {matched_count}")
        print(f"  - Unmatched: {unmatched_count}")
        
        if unmatched_count > 0:
            print("\n⚠️  Unmatched staff names (add to staff_mappings.json if needed):")
            for shift in scheduled_shifts:
                staff_match = checker.staff_matcher.find_staff_match(shift.staff_name, checker.staff_members)
                if not staff_match:
                    print(f"  - Excel: {shift.staff_name} (shift: {shift.shift_code})")
        
        print("\n✅ Basic functionality test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
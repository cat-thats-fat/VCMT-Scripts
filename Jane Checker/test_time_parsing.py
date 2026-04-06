#!/usr/bin/env python3
"""
Test the enhanced time parsing functionality
"""

from jane_shift_checker import ScheduleReader
from datetime import datetime

def test_time_parsing():
    """Test the time parsing functionality"""
    print("Testing Enhanced Legend Time Parsing")
    print("=" * 50)
    
    # Initialize the schedule reader
    reader = ScheduleReader('janechecks26.xlsx')
    
    # Test specific shift codes
    test_shifts = [
        'AM4-1',
        'PM3-1', 
        'CAD #1',
        'Orien + MOCK',
        'FFL',
        'ICORD (O)'
    ]
    
    print("Shift Time Parsing Results:")
    print()
    
    for shift_code in test_shifts:
        time_blocks = reader.get_shift_times(shift_code)
        print(f"{shift_code:15} →", end="")
        
        if time_blocks:
            block_strs = []
            for block in time_blocks:
                block_strs.append(f"{block.start_time}-{block.end_time}")
            print(f" {' + '.join(block_strs)}")
            
            # Show datetime conversion for first block
            if time_blocks:
                test_date = datetime(2026, 7, 28)
                start_dt, end_dt = time_blocks[0].to_datetime(test_date)
                print(f"{'':<15}   First block on {test_date.strftime('%Y-%m-%d')}: {start_dt.strftime('%H:%M')} to {end_dt.strftime('%H:%M')}")
        else:
            print(" No time blocks found")
        print()
    
    # Test a complete schedule for a day
    test_date = datetime(2026, 5, 12)
    shifts = reader.get_shifts_for_date(test_date)
    
    print(f"Sample shifts for {test_date.strftime('%Y-%m-%d')}:")
    print()
    
    for shift in shifts[:5]:
        print(f"{shift.staff_name:20} | {shift.shift_code:15} | Time blocks: {len(shift.time_blocks)}")
        for i, block in enumerate(shift.time_blocks):
            start_dt, end_dt = block.to_datetime(shift.date)
            print(f"{'':<38} Block {i+1}: {start_dt.strftime('%H:%M')} to {end_dt.strftime('%H:%M')}")
    
    print(f"\nTotal shifts with time blocks: {len([s for s in shifts if s.time_blocks])}")
    print(f"Total shifts without time blocks: {len([s for s in shifts if not s.time_blocks])}")

if __name__ == "__main__":
    test_time_parsing()
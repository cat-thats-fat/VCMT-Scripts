#!/usr/bin/env python3
"""
Debug the parsing to see what's going wrong
"""

from jane_shift_checker import ShiftChecker
from datetime import datetime
import json

def debug_single_day():
    """Debug what's happening on a single day"""
    print("🔍 DEBUGGING SINGLE DAY PARSING")
    print("=" * 50)
    
    checker = ShiftChecker('janechecks26.xlsx', 'staff.json', verbose=True)
    test_date = datetime(2026, 5, 4)  # Monday
    
    print(f"Analyzing date: {test_date.strftime('%Y-%m-%d (%A)')}")
    print()
    
    # 1. Debug Excel parsing
    print("📋 EXCEL SCHEDULE ANALYSIS")
    print("-" * 30)
    
    scheduled_shifts = checker.schedule_reader.get_shifts_for_date(test_date)
    print(f"Total shifts found: {len(scheduled_shifts)}")
    
    # Group by shift code
    shift_codes = {}
    staff_names = set()
    
    for shift in scheduled_shifts:
        shift_codes[shift.shift_code] = shift_codes.get(shift.shift_code, 0) + 1
        staff_names.add(shift.staff_name)
    
    print(f"Unique staff members: {len(staff_names)}")
    print("Shift code breakdown:")
    for code, count in sorted(shift_codes.items()):
        print(f"  {code}: {count} assignments")
    
    print()
    print("Sample staff assignments:")
    for shift in scheduled_shifts[:10]:
        time_blocks = " + ".join([f"{b.start_time}-{b.end_time}" for b in shift.time_blocks])
        time_info = f"({time_blocks})" if time_blocks else "(no times)"
        print(f"  - {shift.staff_name}: {shift.shift_code} {time_info}")
    
    print()
    
    # 2. Debug JaneApp API response
    print("🌐 JANEAPP API ANALYSIS")
    print("-" * 30)
    
    # Read the cookie
    try:
        with open('cookies.txt', 'r') as f:
            cookies = f.read().strip()
        
        checker.jane_client.set_session_cookies(cookies)
        jane_shifts = checker.jane_client.get_shifts_for_date(test_date)
        parse_stats = checker.jane_client.last_parse_stats or {}
        
        print(f"Total Jane shifts found: {len(jane_shifts)}")
        if parse_stats:
            print("Parser diagnostics:")
            for key in [
                'raw_records',
                'accepted',
                'skipped_missing_required',
                'skipped_missing_staff',
                'skipped_break',
                'skipped_patient',
                'skipped_parse_error'
            ]:
                print(f"  - {key}: {parse_stats.get(key, 0)}")
        
        if jane_shifts:
            print("Jane shift details:")
            staff_ids_in_jane = set()
            for shift in jane_shifts:
                staff_ids_in_jane.add(shift.staff_member_id)
                # Find staff name
                staff_name = "Unknown"
                for staff in checker.staff_members:
                    if staff.jane_id == shift.staff_member_id:
                        staff_name = staff.professional_name
                        break
                
                print(f"  - ID {shift.staff_member_id} ({staff_name}): {shift.start_at.strftime('%H:%M')}-{shift.end_at.strftime('%H:%M')}")
            
            print(f"Unique staff IDs in Jane: {len(staff_ids_in_jane)}")
        else:
            print("No Jane shifts found - checking API response format...")
            
            # Let's check the raw API response
            import requests
            
            url = f"{checker.jane_client.base_url}/admin/api/v2/calendar"
            params = {
                'start_date': test_date.strftime('%Y-%m-%d'),
                'end_date': test_date.strftime('%Y-%m-%d'),
                'location_id': 1,
                'include_unscheduled': 'false'
            }
            
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest',
            }
            
            try:
                response = checker.jane_client.session.get(url, params=params, headers=headers)
                data = response.json()
                parsed, stats = checker.jane_client._parse_calendar_payload(data)
                
                print("Raw API response structure:")
                print(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                print(f"  Parsed comparable shifts: {len(parsed)}")
                print(f"  Parse stats: {json.dumps(stats)}")
                
                if 'appointments' in data:
                    appointments = data['appointments']
                    print(f"  Appointments found: {len(appointments)}")
                    
                    if appointments:
                        sample = appointments[0]
                        print(f"  Sample appointment keys: {list(sample.keys())}")
                        print(f"  Sample: {json.dumps(sample, default=str)[:300]}...")
                        
                        # Check if these are the right kind of appointments
                        print("\\nAll appointments for this date:")
                        for i, apt in enumerate(appointments):
                            if i < 10:  # Show first 10
                                staff_id = apt.get('staff_member_id', 'No staff ID')
                                start = apt.get('start_at', 'No start')
                                apt_type = apt.get('appointment_type', {}).get('name', 'Unknown type')
                                print(f"    {i+1}: Staff {staff_id}, Start: {start}, Type: {apt_type}")
                
                # Check if there are other relevant keys
                for key, value in data.items():
                    if key != 'appointments':
                        print(f"  Other key '{key}': {type(value)} with {len(value) if hasattr(value, '__len__') else 'N/A'} items")
                
            except Exception as e:
                print(f"Error fetching raw API data: {e}")
    
    except FileNotFoundError:
        print("cookies.txt not found - cannot test JaneApp API")
    except Exception as e:
        print(f"Error testing JaneApp API: {e}")

if __name__ == "__main__":
    debug_single_day()

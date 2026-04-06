#!/usr/bin/env python3
"""
JaneApp Shift Checker
Verifies that all shifts uploaded to JaneApp match the schedule in the Excel file.
"""

import json
import pandas as pd
import argparse
import sys
import re
from contextlib import redirect_stdout
from datetime import datetime, timedelta, date, timezone
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import Counter
from html import escape
from fuzzywuzzy import fuzz, process
import requests
from pathlib import Path

DEFAULT_TIME_TOLERANCE_MINUTES = 15
NON_WORK_SHIFT_PATTERN = re.compile(r'\b(?:NS|ON[\s-]?CALL|OUT[\s-]?REACH)\b', re.IGNORECASE)
OUTREACH_LOCATION_PATTERN = re.compile(r'refer to outreach info sheet', re.IGNORECASE)

@dataclass
class StaffMember:
    """Represents a staff member from the staff.json file"""
    jane_id: int
    first_name: str
    last_name: str
    professional_name: str
    active: bool
    full_name: str = ""
    
    def __post_init__(self):
        self.full_name = f"{self.first_name} {self.last_name}".strip()

@dataclass
class ShiftTimeBlock:
    """Represents a single time block within a shift"""
    start_time: str  # Format: "08:30"
    end_time: str    # Format: "11:30"
    
    def to_datetime(self, date: datetime, tzinfo=None) -> Tuple[datetime, datetime]:
        """Convert time strings to datetime objects for a specific date"""
        start_hour, start_min = map(int, self.start_time.split(':'))
        end_hour, end_min = map(int, self.end_time.split(':'))
        
        start_dt = date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        end_dt = date.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)

        if tzinfo is not None:
            start_dt = start_dt.replace(tzinfo=tzinfo)
            end_dt = end_dt.replace(tzinfo=tzinfo)
        
        return start_dt, end_dt

@dataclass
class ScheduledShift:
    """Represents a shift from the Excel schedule"""
    date: datetime
    staff_name: str
    shift_code: str
    location: str
    hours: float
    day_of_week: str
    time_blocks: List[ShiftTimeBlock] = None
    
    def __post_init__(self):
        if self.time_blocks is None:
            self.time_blocks = []

@dataclass
class JaneShift:
    """Represents a shift from JaneApp API"""
    id: int
    start_at: datetime
    end_at: datetime
    staff_member_id: int
    location_id: int
    notes: Optional[str]
    tags: List[str]

@dataclass
class DateRangeResults:
    """Results from checking a date range"""
    start_date: date
    end_date: date
    total_days: int
    processed_days: int
    daily_results: List[Dict]
    summary: Dict

class StaffMatcher:
    """Handles fuzzy matching of staff names between Excel and JaneApp"""
    
    def __init__(self):
        self.manual_mappings: Dict[str, int] = {}
        self.fuzzy_threshold = 80
        
    def load_manual_mappings(self, mapping_file: str):
        """Load manual name mappings from a file"""
        try:
            with open(mapping_file, 'r') as f:
                self.manual_mappings = json.load(f)
        except FileNotFoundError:
            print(f"Manual mapping file {mapping_file} not found. Will create if needed.")
    
    def save_manual_mappings(self, mapping_file: str):
        """Save manual name mappings to a file"""
        with open(mapping_file, 'w') as f:
            json.dump(self.manual_mappings, f, indent=2)
    
    def find_staff_match(self, staff_name: str, staff_members: List[StaffMember]) -> Optional[StaffMember]:
        """Find matching staff member using various strategies"""
        
        # First check manual mappings (using name as key now)
        if staff_name in self.manual_mappings:
            jane_id = self.manual_mappings[staff_name]
            for staff in staff_members:
                if staff.jane_id == jane_id:
                    return staff
        
        # Try fuzzy name matching
        # Create a list of all name variations for each staff member
        staff_name_variations = []
        for staff in staff_members:
            variations = [
                staff.professional_name,
                staff.full_name,
                f"{staff.first_name}",
                f"{staff.last_name}",
            ]
            staff_name_variations.extend([(var, staff) for var in variations if var.strip()])
        
        # Try to match staff_name against variations
        name_matches = process.extract(staff_name, [var[0] for var in staff_name_variations], limit=3)
        
        for match_name, score in name_matches:
            if score >= self.fuzzy_threshold:
                for var_name, staff in staff_name_variations:
                    if var_name == match_name:
                        return staff
        
        return None

class ScheduleReader:
    """Reads and parses the Excel schedule file"""
    
    def __init__(self, excel_file: str):
        self.excel_file = excel_file
        self.legend = self._load_legend()
        self.shift_times_cache = self._parse_all_shift_times()
        self.last_exclusion_counts = {}
    
    def _load_legend(self) -> pd.DataFrame:
        """Load the legend sheet to understand shift codes"""
        try:
            return pd.read_excel(self.excel_file, sheet_name='legend')
        except Exception as e:
            print(f"Error loading legend: {e}")
            return pd.DataFrame()
    
    def _parse_time_string(self, time_str: str) -> List[ShiftTimeBlock]:
        """Parse a time string into time blocks"""
        if pd.isna(time_str) or time_str == 'nan':
            return []
        
        time_blocks = []
        time_str = str(time_str).strip()
        
        # Handle split shifts with semicolons (e.g., "8:30AM-12PM;1PM-4:30PM")
        if ';' in time_str:
            segments = time_str.split(';')
            for segment in segments:
                blocks = self._parse_single_time_range(segment.strip())
                time_blocks.extend(blocks)
        else:
            time_blocks = self._parse_single_time_range(time_str)
        
        return time_blocks
    
    def _parse_single_time_range(self, time_range: str) -> List[ShiftTimeBlock]:
        """Parse a single time range like '8AM - 3:30PM' or '8:30AM-12PM'"""
        if not time_range or time_range.strip() == '':
            return []
        
        # Skip complex formats for now (like "8/8:15AM - 1:30/1:45PM")
        if '/' in time_range or 'depending' in time_range.lower() or 'double shift' in time_range.lower():
            return []
        
        # Skip formats with multiple time options
        if 'tue:' in time_range.lower() or 'wed:' in time_range.lower():
            return []
        
        # Skip "1st shift:" prefixed entries for now
        if '1st shift:' in time_range.lower():
            time_range = time_range.split('1st shift:')[1].strip()
        
        # Normalize the range separator
        time_range = re.sub(r'\s*-\s*', '-', time_range)
        time_range = re.sub(r'\s*–\s*', '-', time_range)  # em dash
        
        # Split on dash
        if '-' not in time_range:
            return []
        
        parts = time_range.split('-', 1)
        if len(parts) != 2:
            return []
        
        start_str, end_str = parts
        start_time = self._normalize_time(start_str.strip())
        end_time = self._normalize_time(end_str.strip())
        
        if start_time and end_time:
            return [ShiftTimeBlock(start_time, end_time)]
        
        return []
    
    def _normalize_time(self, time_str: str) -> str:
        """Convert time like '8AM', '3:30PM', '12PM' to 24-hour format '08:00', '15:30', '12:00'"""
        if not time_str:
            return ""
        
        # Remove spaces and convert to uppercase
        time_str = time_str.replace(' ', '').upper()
        
        # Extract AM/PM
        is_pm = 'PM' in time_str
        is_am = 'AM' in time_str
        
        # Remove AM/PM indicators
        time_str = time_str.replace('AM', '').replace('PM', '')
        
        # Handle formats like "8", "8:30", "12:15"
        if ':' in time_str:
            hour_str, minute_str = time_str.split(':')
            hour = int(hour_str)
            minute = int(minute_str)
        else:
            hour = int(time_str)
            minute = 0
        
        # Convert to 24-hour format
        if is_pm and hour != 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0
        
        return f"{hour:02d}:{minute:02d}"
    
    def _parse_all_shift_times(self) -> Dict[str, List[ShiftTimeBlock]]:
        """Parse all shift times from the legend into a cache"""
        cache = {}
        
        if self.legend.empty:
            return cache
        
        for idx, row in self.legend.iterrows():
            shift_code = row.get('Tile')
            hours_str = row.get('Hours')
            
            if pd.notna(shift_code) and pd.notna(hours_str):
                time_blocks = self._parse_time_string(hours_str)
                cache[shift_code] = time_blocks
        
        return cache
    
    def get_shift_times(self, shift_code: str) -> List[ShiftTimeBlock]:
        """Get the time blocks for a specific shift code"""
        return self.shift_times_cache.get(shift_code, [])
    
    def get_shifts_for_date(self, target_date: datetime) -> List[ScheduledShift]:
        """Extract shifts for a specific date from the Excel schedule"""
        shifts = []
        exclusion_counts = {
            'blank_or_stat': 0,
            'ns': 0,
            'on_call': 0,
            'outreach': 0,
            'included': 0
        }
        
        # Determine which day of week and find the corresponding sheet
        day_names = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
        day_name = day_names[target_date.weekday()]
        
        try:
            df = pd.read_excel(self.excel_file, sheet_name=day_name)
        except Exception as e:
            print(f"Error loading {day_name} sheet: {e}")
            self.last_exclusion_counts = exclusion_counts
            return shifts
        
        # Find the column for our target date
        target_col = None
        for col in df.columns:
            if isinstance(col, datetime) and col.date() == target_date.date():
                target_col = col
                break
        
        if target_col is None:
            print(f"No column found for date {target_date.date()}")
            self.last_exclusion_counts = exclusion_counts
            return shifts
        
        # Extract shifts from the column
        for idx, row in df.iterrows():
            staff_name = row.get('Week')  # Staff name from Week column
            shift_code = row.get(target_col)
            
            # Skip if no valid staff name or shift
            if pd.isna(staff_name) or pd.isna(shift_code):
                exclusion_counts['blank_or_stat'] += 1
                continue
                
            # Skip header row
            if str(staff_name).strip() in ['Full Name', 'Week']:
                continue
            
            shift_code_str = str(shift_code).strip()
            shift_code_upper = shift_code_str.upper()

            # Skip non-shift entries
            if shift_code_upper in ['STAT', 'NAN', '']:
                exclusion_counts['blank_or_stat'] += 1
                continue
            
            # Skip non-working status / administrative codes
            # Includes NS, ON CALL variants, and OUTREACH variants.
            if shift_code_upper == 'NS':
                exclusion_counts['ns'] += 1
                continue
            if NON_WORK_SHIFT_PATTERN.search(shift_code_str):
                if 'CALL' in shift_code_upper:
                    exclusion_counts['on_call'] += 1
                elif 'OUT' in shift_code_upper and 'REACH' in shift_code_upper:
                    exclusion_counts['outreach'] += 1
                continue
            
            # Look up shift details in legend (normalized exact-match first)
            shift_info = self._lookup_shift_info(shift_code_str)

            # Skip outreach shifts based on legend metadata
            # (covers codes like Lu'Ma, Pacifica, Summit, etc.)
            location_str = str(shift_info.get('location', '') or '')
            if OUTREACH_LOCATION_PATTERN.search(location_str):
                exclusion_counts['outreach'] += 1
                continue

            time_blocks = self.get_shift_times(shift_code_str)
            
            shifts.append(ScheduledShift(
                date=target_date,
                staff_name=str(staff_name).strip(),
                shift_code=shift_code_str,
                location=shift_info.get('location', 'Unknown'),
                hours=shift_info.get('hours', 0.0),
                day_of_week=day_name,
                time_blocks=time_blocks
            ))
            exclusion_counts['included'] += 1
        
        self.last_exclusion_counts = exclusion_counts
        return shifts
    
    def _lookup_shift_info(self, shift_code: str) -> Dict:
        """Look up shift details in the legend"""
        if self.legend.empty:
            return {'location': 'Unknown', 'hours': 0.0}

        shift_code_norm = str(shift_code).strip().lower()

        # Try normalized exact match first
        exact_match = self.legend[
            self.legend['Tile'].astype(str).str.strip().str.lower() == shift_code_norm
        ]
        if not exact_match.empty:
            row = exact_match.iloc[0]
            return {
                'location': row.get('Location', 'Unknown'),
                'hours': row.get('Hours', 0.0)
            }

        return {'location': 'Unknown', 'hours': 0.0}

class DateRangeManager:
    """Manages date range operations and iteration"""
    
    def __init__(self, start_date: date, end_date: date, include_sundays: bool = False):
        self.start_date = start_date
        self.end_date = end_date
        self.include_sundays = include_sundays
        
    def get_working_dates(self) -> List[date]:
        """Get all dates in range, optionally excluding Sundays"""
        dates = []
        current = self.start_date
        
        while current <= self.end_date:
            # Sunday is weekday() == 6
            if self.include_sundays or current.weekday() != 6:
                dates.append(current)
            current += timedelta(days=1)
        
        return dates
    
    def get_total_days(self) -> int:
        """Get total number of days to process"""
        return len(self.get_working_dates())

class JaneAppClient:
    """Handles communication with JaneApp API"""
    
    def __init__(self, base_url: str = "https://vcmt.janeapp.com", verbose: bool = False):
        self.base_url = base_url
        self.session = requests.Session()
        self.rate_limit_delay = 0.5  # seconds between requests
        self.verbose = verbose
        self.last_parse_stats = None
    
    def set_session_cookies(self, cookie_string: str):
        """Set session cookies from browser"""
        # Parse cookie string and set in session
        cookies = {}
        for cookie in cookie_string.split(';'):
            if '=' in cookie:
                key, value = cookie.strip().split('=', 1)
                cookies[key] = value
        self.session.cookies.update(cookies)
    
    def _normalize_shift_records(self, payload) -> List[Dict]:
        """Normalize calendar payload into a list of raw records."""
        if isinstance(payload, list):
            return payload

        if not isinstance(payload, dict):
            return []

        combined = []
        for key in ('appointments', 'shifts', 'data'):
            value = payload.get(key, [])
            if isinstance(value, list):
                combined.extend(value)
            elif isinstance(value, dict):
                combined.append(value)

        if not combined and all(k in payload for k in ('id', 'start_at', 'end_at')):
            combined.append(payload)

        return combined

    def _parse_calendar_payload(self, payload) -> Tuple[List[JaneShift], Dict[str, int]]:
        """Parse raw calendar payload into comparable JaneShift objects plus diagnostics."""
        raw_records = self._normalize_shift_records(payload)
        stats = {
            'raw_records': len(raw_records),
            'accepted': 0,
            'skipped_missing_required': 0,
            'skipped_missing_staff': 0,
            'skipped_break': 0,
            'skipped_patient': 0,
            'skipped_parse_error': 0
        }
        parsed_shifts = []

        for shift_json in raw_records:
            if not isinstance(shift_json, dict):
                stats['skipped_parse_error'] += 1
                continue

            required_fields = ('id', 'start_at', 'end_at')
            if any(field not in shift_json or shift_json[field] in (None, '') for field in required_fields):
                stats['skipped_missing_required'] += 1
                continue

            if not shift_json.get('staff_member_id'):
                stats['skipped_missing_staff'] += 1
                continue

            if shift_json.get('break', False) or shift_json.get('state') == 'break':
                stats['skipped_break'] += 1
                continue

            if shift_json.get('patient_id') is not None:
                stats['skipped_patient'] += 1
                continue

            try:
                start_at_str = str(shift_json['start_at']).replace('Z', '+00:00')
                end_at_str = str(shift_json['end_at']).replace('Z', '+00:00')

                tags_raw = shift_json.get('tags', [])
                if isinstance(tags_raw, list):
                    tags = [tag.get('name', str(tag)) if isinstance(tag, dict) else str(tag) for tag in tags_raw]
                else:
                    tags = [str(tags_raw)]

                parsed_shifts.append(JaneShift(
                    id=shift_json['id'],
                    start_at=datetime.fromisoformat(start_at_str),
                    end_at=datetime.fromisoformat(end_at_str),
                    staff_member_id=shift_json['staff_member_id'],
                    location_id=shift_json.get('location_id', 1),
                    notes=shift_json.get('notes') or shift_json.get('notes_text'),
                    tags=tags
                ))
                stats['accepted'] += 1
            except Exception:
                stats['skipped_parse_error'] += 1

        return parsed_shifts, stats

    def get_shifts_for_date(self, date: datetime, location_id: int = 1) -> List[JaneShift]:
        """Fetch shifts from JaneApp for a specific date"""
        date_str = date.strftime('%Y-%m-%d')
        
        url = f"{self.base_url}/admin/api/v2/calendar"
        params = {
            'start_date': date_str,
            'end_date': date_str,
            'location_id': location_id,
            'include_unscheduled': 'false',
            'browser_tab_id': f'jane_checker_{hash(date_str)}'  # Add browser tab ID like original
        }
        
        headers = {
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
        try:
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            shifts, parse_stats = self._parse_calendar_payload(data)
            self.last_parse_stats = parse_stats
            if self.verbose:
                print(
                    "Parse stats: "
                    f"raw={parse_stats['raw_records']} accepted={parse_stats['accepted']} "
                    f"missing_required={parse_stats['skipped_missing_required']} "
                    f"missing_staff={parse_stats['skipped_missing_staff']} "
                    f"break={parse_stats['skipped_break']} "
                    f"patient={parse_stats['skipped_patient']} "
                    f"parse_error={parse_stats['skipped_parse_error']}"
                )
            return shifts
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching shifts from JaneApp: {e}")
            self.last_parse_stats = {
                'raw_records': 0,
                'accepted': 0,
                'skipped_missing_required': 0,
                'skipped_missing_staff': 0,
                'skipped_break': 0,
                'skipped_patient': 0,
                'skipped_parse_error': 0,
                'request_error': str(e)
            }
            return []
    
    def get_shifts_for_date_range(self, start_date: datetime, end_date: datetime, location_id: int = 1, progress_callback=None) -> Dict[str, List[JaneShift]]:
        """Fetch shifts from JaneApp for a date range"""
        shifts_by_date = {}
        current_date = start_date
        
        while current_date <= end_date:
            if progress_callback:
                progress_callback(current_date)
            
            date_str = current_date.strftime('%Y-%m-%d')
            shifts = self.get_shifts_for_date(current_date, location_id)
            shifts_by_date[date_str] = shifts
            
            # Rate limiting
            if self.rate_limit_delay > 0:
                import time
                time.sleep(self.rate_limit_delay)
            
            current_date += timedelta(days=1)
        
        return shifts_by_date

class ShiftChecker:
    """Main class that orchestrates the shift checking process"""
    
    def __init__(
        self,
        excel_file: str,
        staff_file: str,
        mapping_file: str = "staff_mappings.json",
        verbose: bool = False,
        time_tolerance_minutes: int = DEFAULT_TIME_TOLERANCE_MINUTES
    ):
        self.schedule_reader = ScheduleReader(excel_file)
        self.jane_client = JaneAppClient(verbose=verbose)
        self.staff_matcher = StaffMatcher()
        self.staff_matcher.load_manual_mappings(mapping_file)
        self.mapping_file = mapping_file
        self.verbose = verbose
        self.time_tolerance_minutes = time_tolerance_minutes
        
        # Load staff data
        with open(staff_file, 'r') as f:
            staff_data = json.load(f)
        
        self.staff_members = [
            StaffMember(
                jane_id=s['id'],
                first_name=s['first_name'],
                last_name=s['last_name'],
                professional_name=s['professional_name'],
                active=s['active']
            )
            for s in staff_data if s['active']  # Only active staff
        ]
        
        print(f"Loaded {len(self.staff_members)} active staff members")
    
    def check_date_range(self, start_date: date, end_date: date, cookies: str = None, include_sundays: bool = False, progress_callback=None) -> DateRangeResults:
        """Check shifts for a date range"""
        if cookies:
            self.jane_client.set_session_cookies(cookies)
        
        date_manager = DateRangeManager(start_date, end_date, include_sundays)
        working_dates = date_manager.get_working_dates()
        total_days = len(working_dates)
        
        print(f"\nChecking shifts from {start_date} to {end_date}")
        print(f"Total days to process: {total_days} (Sundays {'included' if include_sundays else 'excluded'})")
        
        daily_results = []
        summary_stats = {
            'total_scheduled_shifts': 0,
            'total_jane_shifts': 0,
            'total_matched_shifts': 0,
            'total_missing_in_jane': 0,
            'total_extra_in_jane': 0,
            'total_name_matching_issues': 0,
            'total_excluded_blank_or_stat': 0,
            'total_excluded_ns': 0,
            'total_excluded_on_call': 0,
            'total_excluded_outreach': 0,
            'total_parse_raw_records': 0,
            'total_parse_accepted': 0,
            'total_parse_skipped_missing_required': 0,
            'total_parse_skipped_missing_staff': 0,
            'total_parse_skipped_break': 0,
            'total_parse_skipped_patient': 0,
            'total_parse_skipped_parse_error': 0,
            'days_processed': 0,
            'days_with_issues': 0
        }
        
        for i, current_date in enumerate(working_dates):
            if progress_callback:
                progress_callback(i + 1, total_days, current_date)
            else:
                print(f"Processing day {i + 1}/{total_days}: {current_date.strftime('%Y-%m-%d (%A)')}")
            
            # Convert date to datetime for existing check_date method
            check_datetime = datetime.combine(current_date, datetime.min.time())
            day_result = self.check_date(check_datetime, cookies)
            
            # Add date info
            day_result['date_obj'] = current_date
            day_result['day_of_week'] = current_date.strftime('%A')
            
            daily_results.append(day_result)
            
            # Update summary stats
            summary_stats['total_scheduled_shifts'] += day_result.get('scheduled_shifts', 0)
            summary_stats['total_jane_shifts'] += day_result.get('jane_shifts', 0)
            summary_stats['total_matched_shifts'] += len(day_result.get('matched_shifts', []))
            summary_stats['total_missing_in_jane'] += len(day_result.get('missing_in_jane', []))
            summary_stats['total_extra_in_jane'] += len(day_result.get('extra_in_jane', []))
            summary_stats['total_name_matching_issues'] += len(day_result.get('name_matching_issues', []))
            exclusion = day_result.get('exclusion_diagnostics', {})
            summary_stats['total_excluded_blank_or_stat'] += exclusion.get('blank_or_stat', 0)
            summary_stats['total_excluded_ns'] += exclusion.get('ns', 0)
            summary_stats['total_excluded_on_call'] += exclusion.get('on_call', 0)
            summary_stats['total_excluded_outreach'] += exclusion.get('outreach', 0)
            parse = day_result.get('parse_diagnostics', {})
            summary_stats['total_parse_raw_records'] += parse.get('raw_records', 0)
            summary_stats['total_parse_accepted'] += parse.get('accepted', 0)
            summary_stats['total_parse_skipped_missing_required'] += parse.get('skipped_missing_required', 0)
            summary_stats['total_parse_skipped_missing_staff'] += parse.get('skipped_missing_staff', 0)
            summary_stats['total_parse_skipped_break'] += parse.get('skipped_break', 0)
            summary_stats['total_parse_skipped_patient'] += parse.get('skipped_patient', 0)
            summary_stats['total_parse_skipped_parse_error'] += parse.get('skipped_parse_error', 0)
            summary_stats['days_processed'] += 1
            
            # Check if day has issues
            has_issues = (
                len(day_result.get('missing_in_jane', [])) > 0 or
                len(day_result.get('extra_in_jane', [])) > 0 or
                len(day_result.get('name_matching_issues', [])) > 0
            )
            
            if has_issues:
                summary_stats['days_with_issues'] += 1
        
        return DateRangeResults(
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            processed_days=summary_stats['days_processed'],
            daily_results=daily_results,
            summary=summary_stats
        )
    
    def check_date(self, check_date: datetime, cookies: str = None) -> Dict:
        """Check shifts for a specific date"""
        if cookies:
            self.jane_client.set_session_cookies(cookies)
        
        print(f"\nChecking shifts for {check_date.strftime('%Y-%m-%d')}")
        
        # Get scheduled shifts from Excel
        scheduled_shifts = self.schedule_reader.get_shifts_for_date(check_date)
        print(f"Found {len(scheduled_shifts)} scheduled shifts in Excel")
        
        # Get actual shifts from JaneApp
        jane_shifts = self.jane_client.get_shifts_for_date(check_date)
        print(f"Found {len(jane_shifts)} shifts in JaneApp")
        
        # Match staff names and compare
        results = {
            'date': check_date.strftime('%Y-%m-%d'),
            'scheduled_shifts': len(scheduled_shifts),
            'jane_shifts': len(jane_shifts),
            'missing_in_jane': [],
            'extra_in_jane': [],
            'name_matching_issues': [],
            'matched_shifts': []
        }
        results['parse_diagnostics'] = self.jane_client.last_parse_stats or {}
        results['exclusion_diagnostics'] = self.schedule_reader.last_exclusion_counts or {}
        
        # Track which Jane shifts have been matched
        matched_jane_shifts = set()
        
        # Check each scheduled shift
        for scheduled in scheduled_shifts:
            staff_match = self.staff_matcher.find_staff_match(scheduled.staff_name, self.staff_members)
            
            if not staff_match:
                results['name_matching_issues'].append({
                    'staff_name': scheduled.staff_name,
                    'shift_code': scheduled.shift_code,
                    'message': 'No matching staff member found in JaneApp',
                    'reason_code': 'no_staff_match',
                    'reason_detail': 'Excel staff name could not be matched to an active Jane staff profile'
                })
                continue
            
            # Look for matching Jane shifts and validate time blocks
            staff_jane_shifts = [js for js in jane_shifts if js.staff_member_id == staff_match.jane_id]
            
            if staff_jane_shifts and scheduled.time_blocks:
                # Validate time blocks against JaneApp shifts
                validation_result = self._validate_time_blocks(
                    scheduled,
                    staff_jane_shifts,
                    time_tolerance_minutes=self.time_tolerance_minutes
                )
                
                if validation_result['fully_matched']:
                    # All time blocks match
                    for jane_shift in validation_result['matched_shifts']:
                        matched_jane_shifts.add(jane_shift.id)
                    
                    results['matched_shifts'].append({
                        'staff_name': staff_match.professional_name,
                        'excel_shift': scheduled.shift_code,
                        'jane_shift_ids': [js.id for js in validation_result['matched_shifts']],
                        'time_blocks_matched': len(validation_result['matched_blocks']),
                        'validation_details': validation_result
                    })
                else:
                    # Partial or no match
                    nearest_shift = None
                    nearest_start_diff = None
                    nearest_end_diff = None
                    if validation_result.get('nearest_candidates'):
                        nearest = validation_result['nearest_candidates'][0]
                        nearest_shift = nearest.get('jane_shift')
                        nearest_start_diff = nearest.get('start_diff_minutes')
                        nearest_end_diff = nearest.get('end_diff_minutes')

                    reason_code = 'missing_expected_time_block'
                    reason_detail = 'Expected time block did not match an available Jane shift'
                    if nearest_shift:
                        reason_code = 'time_offset'
                        reason_detail = (
                            f"Nearest Jane shift is offset by start={nearest_start_diff}m, "
                            f"end={nearest_end_diff}m from expected block"
                        )

                    results['missing_in_jane'].append({
                        'staff_name': staff_match.professional_name,
                        'shift_code': scheduled.shift_code,
                        'expected_hours': scheduled.hours,
                        'expected_time_blocks': [(b.start_time, b.end_time) for b in scheduled.time_blocks],
                        'validation_issues': validation_result.get('issues', []),
                        'reason_code': reason_code,
                        'reason_detail': reason_detail,
                        'nearest_jane_shift': {
                            'id': nearest_shift.id,
                            'start': nearest_shift.start_at.isoformat(),
                            'end': nearest_shift.end_at.isoformat()
                        } if nearest_shift else None,
                        'start_diff_minutes': nearest_start_diff,
                        'end_diff_minutes': nearest_end_diff
                    })
            elif staff_jane_shifts and not scheduled.time_blocks:
                # Staff has Jane shifts but no expected time blocks (e.g., NS, STAT)
                jane_match = staff_jane_shifts[0]  # Take first shift
                matched_jane_shifts.add(jane_match.id)
                
                results['matched_shifts'].append({
                    'staff_name': staff_match.professional_name,
                    'excel_shift': scheduled.shift_code,
                    'jane_shift_id': jane_match.id,
                    'note': 'Matched without time validation (no expected time blocks)',
                    'reason_code': 'no_expected_time_blocks',
                    'reason_detail': 'Legend entry has no parseable time blocks, so only staff-level match was applied'
                })
            else:
                # No Jane shifts found for this staff member
                results['missing_in_jane'].append({
                    'staff_name': staff_match.professional_name,
                    'shift_code': scheduled.shift_code,
                    'expected_hours': scheduled.hours,
                    'expected_time_blocks': [(b.start_time, b.end_time) for b in scheduled.time_blocks] if scheduled.time_blocks else [],
                    'reason_code': 'no_jane_shift_for_staff',
                    'reason_detail': 'No comparable Jane shifts were found for this staff member on this date'
                })
        
        # Check for extra shifts in Jane
        for jane_shift in jane_shifts:
            if jane_shift.id not in matched_jane_shifts:
                # Find staff member name
                staff_match = None
                for staff in self.staff_members:
                    if staff.jane_id == jane_shift.staff_member_id:
                        staff_match = staff
                        break
                
                staff_name = staff_match.professional_name if staff_match else f"ID:{jane_shift.staff_member_id}"
                
                results['extra_in_jane'].append({
                    'staff_name': staff_name,
                    'jane_shift_id': jane_shift.id,
                    'start': jane_shift.start_at.isoformat(),
                    'end': jane_shift.end_at.isoformat(),
                    'tags': jane_shift.tags,
                    'reason_code': 'unexpected_extra_shift',
                    'reason_detail': 'Jane shift had no matching expected Excel time block for the same staff/date',
                    'notes': jane_shift.notes
                })
        
        return results
    
    def _validate_time_blocks(
        self,
        scheduled: ScheduledShift,
        jane_shifts: List[JaneShift],
        time_tolerance_minutes: int = DEFAULT_TIME_TOLERANCE_MINUTES,
        max_split_gap_minutes: int = 90
    ) -> Dict:
        """Validate that JaneApp shifts match the expected time blocks"""
        validation_result = {
            'fully_matched': False,
            'matched_blocks': [],
            'matched_shifts': [],
            'issues': [],
            'unmatched_time_blocks': [],
            'extra_jane_shifts': [],
            'nearest_candidates': []
        }
        
        if not scheduled.time_blocks:
            validation_result['issues'].append('No expected time blocks to validate')
            return validation_result
        
        expected_blocks = scheduled.time_blocks.copy()
        available_jane_shifts = jane_shifts.copy()
        
        # Try to match each expected time block with a Jane shift
        for expected_block in expected_blocks:
            reference_shift = available_jane_shifts[0] if available_jane_shifts else (jane_shifts[0] if jane_shifts else None)
            reference_tz = reference_shift.start_at.tzinfo if reference_shift else None
            expected_start, expected_end = expected_block.to_datetime(scheduled.date, tzinfo=reference_tz)

            if reference_shift and expected_start.tzinfo is None:
                expected_start = expected_start.replace(tzinfo=reference_tz)
                expected_end = expected_end.replace(tzinfo=reference_tz)

            block_matched = False
            
            for i, jane_shift in enumerate(available_jane_shifts):
                # Check if times match within tolerance
                start_diff = abs((jane_shift.start_at - expected_start).total_seconds()) / 60
                end_diff = abs((jane_shift.end_at - expected_end).total_seconds()) / 60
                
                if start_diff <= time_tolerance_minutes and end_diff <= time_tolerance_minutes:
                    # This Jane shift matches this time block
                    validation_result['matched_blocks'].append({
                        'expected_block': (expected_block.start_time, expected_block.end_time),
                        'jane_shift': jane_shift,
                        'jane_shift_ids': [jane_shift.id],
                        'match_type': 'single_shift',
                        'start_diff_minutes': round(start_diff, 1),
                        'end_diff_minutes': round(end_diff, 1)
                    })
                    validation_result['matched_shifts'].append(jane_shift)
                    available_jane_shifts.pop(i)  # Remove matched shift
                    block_matched = True
                    break

            # If no direct match, support AM4-like split shifts in Jane that cover one expected block.
            if not block_matched and len(available_jane_shifts) >= 2:
                split_match = None
                for i in range(len(available_jane_shifts)):
                    for j in range(i + 1, len(available_jane_shifts)):
                        first = available_jane_shifts[i]
                        second = available_jane_shifts[j]
                        if second.start_at < first.start_at:
                            first, second = second, first
                            first_idx, second_idx = j, i
                        else:
                            first_idx, second_idx = i, j

                        gap_minutes = (second.start_at - first.end_at).total_seconds() / 60
                        if gap_minutes < 0 or gap_minutes > max_split_gap_minutes:
                            continue

                        start_diff = abs((first.start_at - expected_start).total_seconds()) / 60
                        end_diff = abs((second.end_at - expected_end).total_seconds()) / 60

                        if start_diff <= time_tolerance_minutes and end_diff <= time_tolerance_minutes:
                            split_match = {
                                'first': first,
                                'second': second,
                                'first_idx': first_idx,
                                'second_idx': second_idx,
                                'start_diff': round(start_diff, 1),
                                'end_diff': round(end_diff, 1),
                                'gap_minutes': round(gap_minutes, 1)
                            }
                            break
                    if split_match:
                        break

                if split_match:
                    validation_result['matched_blocks'].append({
                        'expected_block': (expected_block.start_time, expected_block.end_time),
                        'jane_shift': split_match['first'],
                        'jane_shift_ids': [split_match['first'].id, split_match['second'].id],
                        'match_type': 'split_shift',
                        'start_diff_minutes': split_match['start_diff'],
                        'end_diff_minutes': split_match['end_diff'],
                        'gap_minutes': split_match['gap_minutes']
                    })
                    validation_result['matched_shifts'].append(split_match['first'])
                    validation_result['matched_shifts'].append(split_match['second'])

                    for idx in sorted([split_match['first_idx'], split_match['second_idx']], reverse=True):
                        available_jane_shifts.pop(idx)
                    block_matched = True
            
            if not block_matched:
                nearest_candidate = None
                nearest_score = None
                for jane_shift in jane_shifts:
                    start_diff = abs((jane_shift.start_at - expected_start).total_seconds()) / 60
                    end_diff = abs((jane_shift.end_at - expected_end).total_seconds()) / 60
                    score = start_diff + end_diff
                    if nearest_score is None or score < nearest_score:
                        nearest_score = score
                        nearest_candidate = {
                            'jane_shift': jane_shift,
                            'start_diff_minutes': round(start_diff, 1),
                            'end_diff_minutes': round(end_diff, 1)
                        }

                validation_result['unmatched_time_blocks'].append({
                    'expected_block': (expected_block.start_time, expected_block.end_time),
                    'expected_datetime': (expected_start.isoformat(), expected_end.isoformat()),
                    'nearest_jane_shift': {
                        'id': nearest_candidate['jane_shift'].id,
                        'start': nearest_candidate['jane_shift'].start_at.isoformat(),
                        'end': nearest_candidate['jane_shift'].end_at.isoformat()
                    } if nearest_candidate else None,
                    'start_diff_minutes': nearest_candidate['start_diff_minutes'] if nearest_candidate else None,
                    'end_diff_minutes': nearest_candidate['end_diff_minutes'] if nearest_candidate else None
                })
                if nearest_candidate:
                    validation_result['nearest_candidates'].append(nearest_candidate)
        
        # Any remaining Jane shifts are "extra"
        validation_result['extra_jane_shifts'] = available_jane_shifts
        
        # Determine if fully matched
        validation_result['fully_matched'] = (
            len(validation_result['matched_blocks']) == len(expected_blocks) and
            len(validation_result['extra_jane_shifts']) == 0
        )
        
        # Generate issues summary
        if validation_result['unmatched_time_blocks']:
            validation_result['issues'].append(f"Missing {len(validation_result['unmatched_time_blocks'])} expected time blocks")
        
        if validation_result['extra_jane_shifts']:
            validation_result['issues'].append(f"Found {len(validation_result['extra_jane_shifts'])} unexpected Jane shifts")
        
        return validation_result
    
    def save_unmatched_staff(self):
        """Save staff matching issues for manual resolution"""
        self.staff_matcher.save_manual_mappings(self.mapping_file)

def main():
    parser = argparse.ArgumentParser(description='Check JaneApp shifts against Excel schedule')
    
    # Date options - either single date or date range
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument('--date', help='Single date to check (YYYY-MM-DD)')
    date_group.add_argument('--start-date', help='Start date for range check (YYYY-MM-DD)')
    
    parser.add_argument('--end-date', help='End date for range check (YYYY-MM-DD, required with --start-date)')
    parser.add_argument('--include-sundays', action='store_true', help='Include Sundays in date range')
    parser.add_argument('--excel', default='janechecks26.xlsx', help='Excel schedule file')
    parser.add_argument('--staff', default='staff.json', help='Staff JSON file')
    parser.add_argument('--cookies', help='Browser cookies for JaneApp authentication')
    parser.add_argument('--output', choices=['console', 'json'], default='console', help='Output format')
    parser.add_argument('--report-file', help='Save detailed report to file (HTML format)')
    parser.add_argument('--time-tolerance-minutes', type=int, default=DEFAULT_TIME_TOLERANCE_MINUTES,
                        help='Allowed time difference in minutes when matching shifts')
    parser.add_argument('--verbose', action='store_true', help='Show API parsing diagnostics')
    
    args = parser.parse_args()
    
    # Validate date arguments
    if args.start_date and not args.end_date:
        print("Error: --end-date is required when using --start-date")
        sys.exit(1)
    
    if args.end_date and not args.start_date:
        print("Error: --start-date is required when using --end-date")
        sys.exit(1)
    
    json_mode = args.output == 'json'
    
    if args.date:
        # Single date check
        try:
            check_date = datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)

        if json_mode:
            with redirect_stdout(sys.stderr):
                checker = ShiftChecker(
                    args.excel,
                    args.staff,
                    verbose=args.verbose,
                    time_tolerance_minutes=args.time_tolerance_minutes
                )
                results = checker.check_date(check_date, args.cookies)
                checker.save_unmatched_staff()
            output = {
                'metadata': {
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'input_file': args.excel,
                    'staff_file': args.staff,
                    'time_tolerance_minutes': args.time_tolerance_minutes,
                    'include_sundays': False,
                    'mode': 'single_date'
                },
                'result': results
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            checker = ShiftChecker(
                args.excel,
                args.staff,
                verbose=args.verbose,
                time_tolerance_minutes=args.time_tolerance_minutes
            )
            results = checker.check_date(check_date, args.cookies)
            print_single_date_results(results)
            checker.save_unmatched_staff()
    
    else:
        # Date range check
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
        
        if start_date > end_date:
            print("Error: start-date must be before or equal to end-date")
            sys.exit(1)

        if json_mode:
            with redirect_stdout(sys.stderr):
                checker = ShiftChecker(
                    args.excel,
                    args.staff,
                    verbose=args.verbose,
                    time_tolerance_minutes=args.time_tolerance_minutes
                )
                results = checker.check_date_range(
                    start_date,
                    end_date,
                    args.cookies,
                    args.include_sundays
                )
                if args.report_file:
                    generate_html_report(results, args.report_file)
                    print(f"\nDetailed report saved to: {args.report_file}")
                checker.save_unmatched_staff()
        else:
            checker = ShiftChecker(
                args.excel,
                args.staff,
                verbose=args.verbose,
                time_tolerance_minutes=args.time_tolerance_minutes
            )
            results = checker.check_date_range(
                start_date,
                end_date,
                args.cookies,
                args.include_sundays
            )
            print_date_range_results(results)
            if args.report_file:
                generate_html_report(results, args.report_file)
                print(f"\nDetailed report saved to: {args.report_file}")
            checker.save_unmatched_staff()

        if json_mode:
            # Convert date objects to strings for JSON serialization
            results_dict = {
                'metadata': {
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'input_file': args.excel,
                    'staff_file': args.staff,
                    'time_tolerance_minutes': args.time_tolerance_minutes,
                    'include_sundays': args.include_sundays,
                    'mode': 'date_range'
                },
                'start_date': str(results.start_date),
                'end_date': str(results.end_date),
                'total_days': results.total_days,
                'processed_days': results.processed_days,
                'summary': results.summary,
                'daily_results': results.daily_results
            }
            print(json.dumps(results_dict, indent=2, default=str))

def print_single_date_results(results):
    """Print results for a single date in console format"""
    print(f"\n=== SHIFT CHECK RESULTS FOR {results['date']} ===")
    print(f"Scheduled shifts: {results['scheduled_shifts']}")
    print(f"JaneApp shifts: {results['jane_shifts']}")
    print(f"Matched shifts: {len(results['matched_shifts'])}")
    
    if results['missing_in_jane']:
        print(f"\n⚠️  MISSING IN JANEAPP ({len(results['missing_in_jane'])} shifts):")
        for missing in results['missing_in_jane']:
            print(f"  - {missing['staff_name']}: {missing['shift_code']} ({missing['expected_hours']} hours)")
    
    if results['extra_in_jane']:
        print(f"\n⚠️  EXTRA IN JANEAPP ({len(results['extra_in_jane'])} shifts):")
        for extra in results['extra_in_jane']:
            print(f"  - {extra['staff_name']}: {extra['start']} to {extra['end']}")
    
    if results['name_matching_issues']:
        print(f"\n⚠️  NAME MATCHING ISSUES ({len(results['name_matching_issues'])} issues):")
        for issue in results['name_matching_issues']:
            print(f"  - Staff '{issue['staff_name']}' ({issue['shift_code']}): {issue['message']}")
    
    if not any([results['missing_in_jane'], results['extra_in_jane'], results['name_matching_issues']]):
        print("\n✅ All shifts match perfectly!")

def print_date_range_results(results: DateRangeResults):
    """Print results for a date range in console format"""
    print(f"\n=== DATE RANGE SHIFT CHECK RESULTS ===")
    print(f"Period: {results.start_date} to {results.end_date}")
    print(f"Days processed: {results.processed_days}/{results.total_days}")
    print()
    
    # Summary statistics
    summary = results.summary
    print("📊 SUMMARY STATISTICS")
    print(f"  Total scheduled shifts: {summary['total_scheduled_shifts']}")
    print(f"  Total JaneApp shifts: {summary['total_jane_shifts']}")
    print(f"  Total matched shifts: {summary['total_matched_shifts']}")
    print(f"  Days with issues: {summary['days_with_issues']}")
    print()
    
    if summary['total_missing_in_jane'] > 0:
        print(f"⚠️  MISSING IN JANEAPP: {summary['total_missing_in_jane']} shifts across {summary['days_with_issues']} days")
    
    if summary['total_extra_in_jane'] > 0:
        print(f"⚠️  EXTRA IN JANEAPP: {summary['total_extra_in_jane']} shifts")
    
    if summary['total_name_matching_issues'] > 0:
        print(f"⚠️  NAME MATCHING ISSUES: {summary['total_name_matching_issues']} issues")
    
    # Daily breakdown for days with issues
    problematic_days = [day for day in results.daily_results if 
                       len(day.get('missing_in_jane', [])) > 0 or
                       len(day.get('extra_in_jane', [])) > 0 or 
                       len(day.get('name_matching_issues', [])) > 0]
    
    if problematic_days:
        print(f"\n📅 DAILY BREAKDOWN ({len(problematic_days)} days with issues):")
        for day in problematic_days[:10]:  # Show first 10 days with issues
            print(f"\n  {day['date']} ({day['day_of_week']}):")
            if day.get('missing_in_jane'):
                print(f"    Missing: {len(day['missing_in_jane'])} shifts")
            if day.get('extra_in_jane'):
                print(f"    Extra: {len(day['extra_in_jane'])} shifts")  
            if day.get('name_matching_issues'):
                print(f"    Name issues: {len(day['name_matching_issues'])} issues")
        
        if len(problematic_days) > 10:
            print(f"\n    ... and {len(problematic_days) - 10} more days with issues")
    
    if summary['days_with_issues'] == 0:
        print("\n✅ All shifts match perfectly across all days!")

def generate_html_report(results: DateRangeResults, filename: str):
    """Generate an HTML report for date range results"""
    missing_codes = Counter()
    affected_staff = Counter()
    reason_codes = Counter()
    exclusion_totals = Counter()

    for day in results.daily_results:
        for item in day.get('missing_in_jane', []):
            missing_codes[item.get('shift_code', 'Unknown')] += 1
            affected_staff[item.get('staff_name', 'Unknown')] += 1
            reason_codes[item.get('reason_code', 'unknown')] += 1
        for item in day.get('extra_in_jane', []):
            affected_staff[item.get('staff_name', 'Unknown')] += 1
            reason_codes[item.get('reason_code', 'unknown')] += 1
        exclusion = day.get('exclusion_diagnostics', {})
        for key in ('blank_or_stat', 'ns', 'on_call', 'outreach'):
            exclusion_totals[key] += exclusion.get(key, 0)

    total_scheduled = results.summary.get('total_scheduled_shifts', 0)
    total_matched = results.summary.get('total_matched_shifts', 0)
    matched_rate = (total_matched / total_scheduled) if total_scheduled else 0.0
    time_offset_count = reason_codes.get('time_offset', 0)
    total_discrepancies = sum(reason_codes.values()) or 1
    time_offset_ratio = time_offset_count / total_discrepancies

    warning_messages = []
    if matched_rate < 0.5:
        warning_messages.append(
            f"Low matched rate detected ({matched_rate:.1%}). Review shift templates and tolerance assumptions."
        )
    if time_offset_ratio > 0.35 and time_offset_count > 10:
        warning_messages.append(
            f"High time-offset pattern detected ({time_offset_count} discrepancies). "
            "This may indicate systemic legend/template time drift."
        )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>JaneApp Shift Check Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; color: #1b1b1b; }}
            .summary {{ background: #f6f7f8; padding: 16px; border-radius: 6px; margin-bottom: 16px; }}
            .warning {{ background: #fff4e5; border: 1px solid #f0b429; padding: 12px; border-radius: 6px; margin-bottom: 12px; }}
            .issue {{ color: #b42318; }}
            .success {{ color: #027a48; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 10px; margin-bottom: 16px; }}
            th, td {{ border: 1px solid #d0d5dd; padding: 8px; text-align: left; vertical-align: top; }}
            th {{ background-color: #f2f4f7; }}
            .section {{ margin-top: 18px; }}
            details {{ margin: 10px 0 18px 0; border: 1px solid #d0d5dd; border-radius: 6px; padding: 8px; }}
            summary {{ cursor: pointer; font-weight: 600; }}
            .mono {{ font-family: monospace; }}
        </style>
    </head>
    <body>
        <h1>JaneApp Shift Check Report</h1>
        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Period:</strong> {escape(str(results.start_date))} to {escape(str(results.end_date))}</p>
            <p><strong>Days Processed:</strong> {results.processed_days}/{results.total_days}</p>
            <p><strong>Scheduled:</strong> {total_scheduled} |
               <strong>Jane:</strong> {results.summary.get('total_jane_shifts', 0)} |
               <strong>Matched:</strong> {total_matched} ({matched_rate:.1%})</p>
            <p><strong>Missing:</strong> {results.summary.get('total_missing_in_jane', 0)} |
               <strong>Extra:</strong> {results.summary.get('total_extra_in_jane', 0)} |
               <strong>Name Issues:</strong> {results.summary.get('total_name_matching_issues', 0)}</p>
        </div>
    """

    for msg in warning_messages:
        html_content += f'<div class="warning"><strong>Warning:</strong> {escape(msg)}</div>'

    def render_rollup_table(title: str, rows):
        nonlocal html_content
        html_content += f'<div class="section"><h2>{escape(title)}</h2><table><tr><th>Item</th><th>Count</th></tr>'
        for key, count in rows:
            html_content += f"<tr><td>{escape(str(key))}</td><td>{count}</td></tr>"
        html_content += "</table></div>"

    render_rollup_table("Top Missing Shift Codes", missing_codes.most_common(15))
    render_rollup_table("Top Affected Staff", affected_staff.most_common(20))
    render_rollup_table("Discrepancy Reasons", reason_codes.most_common(15))
    render_rollup_table(
        "Excluded From Comparison",
        [('blank_or_stat', exclusion_totals['blank_or_stat']),
         ('ns', exclusion_totals['ns']),
         ('on_call', exclusion_totals['on_call']),
         ('outreach', exclusion_totals['outreach'])]
    )

    html_content += """
    <div class="section">
        <h2>Daily Summary</h2>
        <table>
            <tr>
                <th>Date</th>
                <th>Day</th>
                <th>Scheduled</th>
                <th>Jane</th>
                <th>Matched</th>
                <th>Missing</th>
                <th>Extra</th>
                <th>Name Issues</th>
            </tr>
    """

    for day in results.daily_results:
        missing = len(day.get('missing_in_jane', []))
        extra = len(day.get('extra_in_jane', []))
        issues = len(day.get('name_matching_issues', []))
        status_class = 'issue' if (missing + extra + issues) > 0 else 'success'
        html_content += f"""
            <tr class="{status_class}">
                <td>{escape(day['date'])}</td>
                <td>{escape(day.get('day_of_week', ''))}</td>
                <td>{day.get('scheduled_shifts', 0)}</td>
                <td>{day.get('jane_shifts', 0)}</td>
                <td>{len(day.get('matched_shifts', []))}</td>
                <td>{missing}</td>
                <td>{extra}</td>
                <td>{issues}</td>
            </tr>
        """

    html_content += "</table></div>"

    for day in results.daily_results:
        missing = day.get('missing_in_jane', [])
        extra = day.get('extra_in_jane', [])
        name_issues = day.get('name_matching_issues', [])
        if not (missing or extra or name_issues):
            continue

        html_content += (
            f"<details><summary>{escape(day['date'])} ({escape(day.get('day_of_week', ''))}) - "
            f"Missing {len(missing)}, Extra {len(extra)}, Name issues {len(name_issues)}</summary>"
        )

        if missing:
            html_content += """
            <h3>Missing In Jane</h3>
            <table>
                <tr>
                    <th>Staff</th>
                    <th>Shift Code</th>
                    <th>Expected Time Blocks</th>
                    <th>Validation Issues</th>
                    <th>Nearest Jane Shift</th>
                    <th>Reason</th>
                </tr>
            """
            for item in missing:
                blocks = item.get('expected_time_blocks', [])
                block_text = ", ".join([f"{b[0]}-{b[1]}" for b in blocks]) if blocks else "N/A"
                nearest = item.get('nearest_jane_shift')
                nearest_text = (
                    f"{nearest.get('start')} to {nearest.get('end')}<br>"
                    f"Δstart={item.get('start_diff_minutes')}m, Δend={item.get('end_diff_minutes')}m"
                ) if nearest else "N/A"
                html_content += f"""
                <tr>
                    <td>{escape(str(item.get('staff_name', '')))}</td>
                    <td>{escape(str(item.get('shift_code', '')))}</td>
                    <td class="mono">{escape(block_text)}</td>
                    <td>{escape('; '.join(item.get('validation_issues', [])) or 'N/A')}</td>
                    <td>{nearest_text}</td>
                    <td><strong>{escape(str(item.get('reason_code', 'unknown')))}</strong><br>{escape(str(item.get('reason_detail', '')))}</td>
                </tr>
                """
            html_content += "</table>"

        if extra:
            html_content += """
            <h3>Extra In Jane</h3>
            <table>
                <tr>
                    <th>Staff</th>
                    <th>Jane Shift ID</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>Tags/Notes</th>
                    <th>Reason</th>
                </tr>
            """
            for item in extra:
                tags_text = ", ".join(item.get('tags', [])) if item.get('tags') else "N/A"
                notes = item.get('notes') or ''
                html_content += f"""
                <tr>
                    <td>{escape(str(item.get('staff_name', '')))}</td>
                    <td>{escape(str(item.get('jane_shift_id', '')))}</td>
                    <td class="mono">{escape(str(item.get('start', '')))}</td>
                    <td class="mono">{escape(str(item.get('end', '')))}</td>
                    <td>{escape(tags_text)}{'<br>' + escape(notes) if notes else ''}</td>
                    <td><strong>{escape(str(item.get('reason_code', 'unknown')))}</strong><br>{escape(str(item.get('reason_detail', '')))}</td>
                </tr>
                """
            html_content += "</table>"

        if name_issues:
            html_content += """
            <h3>Name Matching Issues</h3>
            <table>
                <tr>
                    <th>Staff</th>
                    <th>Shift Code</th>
                    <th>Reason</th>
                </tr>
            """
            for item in name_issues:
                html_content += f"""
                <tr>
                    <td>{escape(str(item.get('staff_name', '')))}</td>
                    <td>{escape(str(item.get('shift_code', '')))}</td>
                    <td>{escape(str(item.get('reason_code', item.get('message', ''))))}<br>{escape(str(item.get('reason_detail', '')))}</td>
                </tr>
                """
            html_content += "</table>"

        parse_diag = day.get('parse_diagnostics', {})
        exclusion_diag = day.get('exclusion_diagnostics', {})
        html_content += (
            "<p><strong>Diagnostics:</strong> "
            f"parse={escape(json.dumps(parse_diag))} | "
            f"excluded={escape(json.dumps(exclusion_diag))}</p>"
        )
        html_content += "</details>"

    html_content += "</body></html>"

    with open(filename, 'w') as f:
        f.write(html_content)

if __name__ == "__main__":
    main()

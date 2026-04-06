# JaneApp Shift Checker

This tool verifies that all shifts uploaded to JaneApp match the schedule defined in the Excel file.

## Features

- ✅ Compares Excel schedule with JaneApp shifts for any given date
- ✅ Date range checks with optional Sunday inclusion
- ✅ Fuzzy name matching to handle slight variations in staff names
- ✅ Manual mapping system for problematic staff name matches
- ✅ Time block validation with configurable tolerance (default ±15 minutes)
- ✅ Excludes on-call and outreach shifts as specified
- ✅ Ignores admin break overlays and patient-booked appointments during shift comparison
- ✅ Detailed reporting of discrepancies
- ✅ JSON and console output formats

## Setup

1. Install Python dependencies:
```bash
source jane_checker_env/bin/activate
pip install pandas openpyxl requests fuzzywuzzy python-levenshtein
```

2. Ensure you have the required files:
   - `janechecks26.xlsx` - The schedule with legend
   - `staff.json` - Staff member data from JaneApp
   - `staff_mappings.json` - Manual name mappings (created automatically)

## Usage

### Basic Usage

Check shifts for a specific date:
```bash
python jane_shift_checker.py --date 2026-05-12
```

### With JaneApp Authentication

To fetch live data from JaneApp, you'll need to provide browser cookies:

1. Log into JaneApp in your browser
2. Open Developer Tools (F12) → Network tab
3. Make a request to the calendar API
4. Copy the `Cookie` header value
5. Use it with the tool:

```bash
python jane_shift_checker.py --date 2026-05-12 --cookies "your_cookie_string_here"
```

Cookie file workflow:
```bash
echo "cookies_enabled=true; _front_desk_session=..." > cookies.txt
python jane_shift_checker.py --date 2026-05-12 --cookies "$(cat cookies.txt)"
```

### Date Range Checks

```bash
python jane_shift_checker.py --start-date 2026-05-04 --end-date 2026-08-15 --cookies "$(cat cookies.txt)"
```

Include Sundays:
```bash
python jane_shift_checker.py --start-date 2026-05-04 --end-date 2026-08-15 --include-sundays --cookies "$(cat cookies.txt)"
```

Verbose parser diagnostics:
```bash
python jane_shift_checker.py --date 2026-05-12 --cookies "$(cat cookies.txt)" --verbose
```

Custom tolerance:
```bash
python jane_shift_checker.py --date 2026-05-12 --cookies "$(cat cookies.txt)" --time-tolerance-minutes 10
```

### Output Options

Console output (default):
```bash
python jane_shift_checker.py --date 2026-05-12
```

JSON output:
```bash
python jane_shift_checker.py --date 2026-05-12 --output json
```

### Custom Files

Use different input files:
```bash
python jane_shift_checker.py --date 2026-05-12 \
  --excel custom_schedule.xlsx \
  --staff custom_staff.json
```

## Understanding the Output

### Console Output

The tool will show:
- **Total counts**: Scheduled vs JaneApp shifts
- **Missing in JaneApp**: Shifts in Excel but not in JaneApp
- **Extra in JaneApp**: Shifts in JaneApp but not in Excel  
- **Name matching issues**: Staff IDs that couldn't be matched

### JSON Output

Structured data including:
- `metadata`: Run context (`generated_at`, input files, tolerance, mode)
- `scheduled_shifts`: Count of shifts in Excel
- `jane_shifts`: Count of shifts in JaneApp
- `missing_in_jane`: Array of missing shifts
- `extra_in_jane`: Array of extra shifts
- `name_matching_issues`: Array of matching problems
- `matched_shifts`: Array of successfully matched shifts
- `parse_diagnostics`: Jane API parse counters
- `exclusion_diagnostics`: Excel exclusion counters (`ns`, `on_call`, `outreach`, `blank_or_stat`)

Each discrepancy now includes:
- `reason_code` and `reason_detail`
- nearest-shift time deltas (`start_diff_minutes`, `end_diff_minutes`) for offset diagnosis when applicable

## Handling Name Matching Issues

When the tool can't match a staff member between Excel and JaneApp:

1. The issue will be reported in the output
2. Check the `staff_mappings.json` file
3. Add manual mappings in this format:
   ```json
   {
     "8002926": 1597,
     "8002803": 1659
   }
   ```
4. Re-run the tool

## Configuration

Edit `config.json` to customize:
- JaneApp URL and location ID
- File paths
- Fuzzy matching threshold
- Excluded shift keywords

## Data Structure

### Excel Schedule Format
- Multiple sheets: `legend`, `mon`, `tue`, `wed`, `thu`, `fri`, `sat`
- Staff IDs in first column
- Dates as column headers
- Shift codes in cells

### Staff JSON Format
```json
{
  "id": 1597,
  "first_name": "John",
  "last_name": "Doe", 
  "professional_name": "John Doe",
  "active": true
}
```

### JaneApp API Response
The tool expects responses matching the format shown in `request⁄response.txt`.
Comparable shifts are parsed from `appointments` and `shifts`, then filtered to keep real staff shifts only:
- Requires `staff_member_id`, `id`, `start_at`, and `end_at`
- Excludes break overlays (`break: true` or `state: "break"`)
- Excludes patient-booked records (`patient_id` present)

## Troubleshooting

### "No module named 'pandas'"
Make sure you're in the virtual environment:
```bash
source jane_checker_env/bin/activate
```

### "No matching staff member found"
Add manual mappings to `staff_mappings.json` or check if the staff member is active.

### "Error fetching shifts from JaneApp"
Verify your cookies are current and valid. You may need to refresh them from your browser.

### HTML report only shows counts
Use `--report-file` with current build: report now includes full per-shift missing/extra tables, reason codes, and diagnostics by day.

### "No column found for date"
Ensure the date exists as a column header in the corresponding day sheet of the Excel file.

#!/usr/bin/env python3
"""
Helper script to create staff mappings between Excel and JaneApp
"""

import json
import pandas as pd
from fuzzywuzzy import fuzz, process
from jane_shift_checker import ShiftChecker

def analyze_mapping_needs():
    """Analyze what staff mappings are needed"""
    print("Analyzing mapping requirements...")
    
    # Load the checker
    checker = ShiftChecker('janechecks26.xlsx', 'staff.json')
    
    # Get all unique staff names from all days
    all_staff_names = set()
    
    days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat']
    
    for day in days:
        try:
            df = pd.read_excel('janechecks26.xlsx', sheet_name=day)
            # Get staff names from Week column
            staff_names = df['Week'].dropna()
            for staff_name in staff_names:
                name = str(staff_name).strip()
                if name not in ['Full Name', 'Week', '']:  # Skip headers
                    all_staff_names.add(name)
        except Exception as e:
            print(f"Error reading {day}: {e}")
    
    print(f"Found {len(all_staff_names)} unique staff names")
    print(f"Have {len(checker.staff_members)} active JaneApp staff members")
    
    # Create mapping suggestions
    suggestions = {}
    unmatched = []
    
    for staff_name in sorted(all_staff_names):
        # Try to find a match
        staff_match = checker.staff_matcher.find_staff_match(staff_name, checker.staff_members)
        
        if staff_match:
            suggestions[staff_name] = {
                'jane_id': staff_match.jane_id,
                'name': staff_match.professional_name,
                'confidence': 'auto'
            }
        else:
            unmatched.append(staff_name)
    
    print(f"\nAuto-matched: {len(suggestions)}")
    print(f"Need manual mapping: {len(unmatched)}")
    
    # Show staff members for manual matching
    if unmatched:
        print(f"\n=== STAFF NAMES NEEDING MANUAL MAPPING ===")
        print("Excel names that need mapping:")
        for staff_name in unmatched[:20]:  # Show first 20
            print(f"  - {staff_name}")
        
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more")
        
        print(f"\nAvailable JaneApp staff members:")
        for staff in checker.staff_members[:30]:  # Show first 30
            print(f"  - ID {staff.jane_id}: {staff.professional_name}")
        
        if len(checker.staff_members) > 30:
            print(f"  ... and {len(checker.staff_members) - 30} more")
    
    # Save current auto-mappings
    if suggestions:
        mapping_file = {}
        for staff_name, info in suggestions.items():
            mapping_file[staff_name] = info['jane_id']
        
        with open('suggested_mappings.json', 'w') as f:
            json.dump(mapping_file, f, indent=2)
        
        print(f"\n✅ Saved {len(mapping_file)} auto-mappings to 'suggested_mappings.json'")
        print("Review and copy to 'staff_mappings.json' as needed")
    
    # Create a template for manual mappings
    template = {
        "_comment": "Add manual mappings here in format Staff_Name: JaneApp_ID",
        "_instructions": "Find staff names in the unmatched list above and match with JaneApp staff IDs"
    }
    
    # Add some examples of unmatched names
    for i, staff_name in enumerate(unmatched[:5]):
        template[f"_example_{i+1}"] = f"Put JaneApp ID for {staff_name} here"
    
    with open('manual_mapping_template.json', 'w') as f:
        json.dump(template, f, indent=2)
    
    print("✅ Created 'manual_mapping_template.json' for manual entries")
    
    return suggestions, unmatched

def search_staff_by_name():
    """Interactive staff search by name"""
    checker = ShiftChecker('janechecks26.xlsx', 'staff.json')
    
    print("\n=== INTERACTIVE STAFF SEARCH ===")
    print("Enter names to search for matching staff members")
    print("Type 'quit' to exit")
    
    while True:
        query = input("\nSearch for name: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            break
        
        if not query:
            continue
        
        # Search through staff names
        names = []
        staff_lookup = {}
        
        for staff in checker.staff_members:
            for name_variant in [staff.professional_name, staff.full_name, 
                               staff.first_name, staff.last_name]:
                if name_variant.strip():
                    names.append(name_variant)
                    staff_lookup[name_variant] = staff
        
        matches = process.extract(query, names, limit=10)
        
        print(f"\nTop matches for '{query}':")
        for name, score in matches:
            if score >= 50:  # Show decent matches
                staff = staff_lookup[name]
                print(f"  {score}% - ID {staff.jane_id}: {staff.professional_name} ({name})")

if __name__ == "__main__":
    print("JaneApp Staff Mapping Helper")
    print("=" * 40)
    
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'search':
        search_staff_by_name()
    else:
        analyze_mapping_needs()
        print("\nTo search for staff by name, run:")
        print("python create_mappings.py search")
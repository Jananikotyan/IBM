# -*- coding: utf-8 -*-
"""
Quick test for the facility location extraction fix
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

tests = [
    'find nearest hospital near mangalore',
    'nearest hospital in mangalore',
    'hospital near bangalore',
    'find phc near delhi',
    'nearest doctor at mysore',
    'hospital in 575001',
    'nearest hospital near me',
    'hospital near chennai please',
    'find clinic in hyderabad',
]

print("=== Location Extraction Test ===\n")
all_pass = True
for user_input in tests:
    pincode_match = re.search(r'\b\d{6}\b', user_input)
    location_match = re.search(
        r'(?:near(?:est)?|in|at|around)\s+([A-Za-z][\w\s]{1,28}?)(?:\s*\?|$|\.|,)',
        user_input, re.IGNORECASE
    )
    if not location_match:
        location_match = re.search(
            r'(?:hospital|clinic|phc|doctor|health\s+cent(?:re|er))\s+.*?([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\s*(?:\?|$|\.|,)?$',
            user_input, re.MULTILINE
        )
    location = (
        pincode_match.group(0) if pincode_match
        else location_match.group(1).strip() if location_match
        else user_input
    )
    # Check: for "near mangalore" queries, location should be the city not the full sentence
    is_city = len(location.split()) <= 3 and location.lower() not in ['me', 'nearest', 'hospital']
    status = "PASS" if is_city or pincode_match else "WARN"
    if status != "PASS":
        all_pass = False
    print(f"  [{status}] \"{user_input}\"")
    print(f"          -> extracted: \"{location}\"")

print()
print("All location tests OK!" if all_pass else "Some extractions need review.")

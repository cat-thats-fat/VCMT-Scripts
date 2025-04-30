# VCMT Scripts
A collection of scripts to make working at VCMT a little bit easier.

## CMTCA Shift Checker
This is a script that takes json file(s) containing a cohort's schedule(s) from SAZED and ouputs a spreadsheet with which shifts each cohort member attended and a count of how many times.

### Requirements:
- Python
- Pandas

### Usage:
1. Create a folder named "data" in the same directory as the script.
2. Go to the "Schedule" tab of SAZED.
3. Open the Developer console in your browser and go to the network tab.
4. Clear the current outputs inside the network tab.
5. Choose the cohort and semester you want.
6. Look for a request with GetShiftsByCohort.
7. Copy the response of that request to a json file inside the aformentioned folder "data"
8. Repeat steps 4-7 as needed.
9. Run the script.

## Student File Checker
This is a script that will browse all of the clinic's studnet permanant records and generate a HTML report of which students are missing which files and provide a button directly to their folder for ease of access.



# VCMT Scripts

A collection of scripts and browser extensions to make working at VCMT a little bit easier.

This repository contains a mix of automation tools for JaneApp workflows, schedule processing, and clinic file checks.

## JaneApp Helper Extensions

A set of small browser extensions built to speed up repetitive JaneApp admin tasks.

These extensions are intended for internal workflow use and depend on JaneApp’s current URL structure and interface. If JaneApp changes its layout or routing behavior, the scripts will need to be updated.

### 1. Jane ID +1  
**Purpose:** Checking online booking status

This extension is a simple navigation tool for moving between staff profiles one ID at a time while checking their Online Booking settings.

When used on a Jane staff page, it reads the current staff ID from the URL, adds `1` to open the next staff member and then opens the Online Booking tab. This is useful when checking multiple staff profiles in sequence without manually editing the URL each time.

#### What it does
- Detects the current staff ID in the URL
- Increments the ID by 1
- Opens the next staff page
- Open Online Booking settings tab

#### Example
From:

`https://vcmt.janeapp.com/admin#staff/1732/edit`

To:

`https://vcmt.janeapp.com/admin#staff/1733/edit`

#### Use case
Use this when reviewing staff one by one, especially when checking availability or quickly moving through a range of staff records.

#### How to use
1. Open a Jane staff page
2. Check the first student's settings manually
3. Click the extension button
4. The extension will take you to the next staff ID

---

### 2. Jane ID +1 and Rolling Availability  
**Purpose:** Changing availability / booking settings

This extension automates part of the staff availability workflow.

It opens the current staff member’s edit page, clicks **Online Booking**, changes the booking window field to the configured value(1 Month is default), saves the change, and then moves to the next staff member.

This is meant for applying the same availability-related setting across many staff records with less repetitive work.

#### What it does
- Opens the current staff member’s `/edit` page
- Clicks **Online Booking**
- Sets the `max_bookable_offset` field
- Saves the change
- Moves to the next staff member

#### Current configured value
The script is currently set to:

`2628000`

This corresponds to the “1 month” option used in JaneApp.

#### Use case
Use this when updating the same online booking / rolling availability setting across multiple staff records.

#### How to use
1. Open a Jane staff page
2. Click the extension button
3. Wait for the script to:
   - open the edit page
   - open **Online Booking**
   - update the setting
   - save
   - move to the next staff member

#### Important note
Because JaneApp is a dynamic web app, timing can matter. If the page does not fully load or Jane changes its interface, the script may need small updates.

---

### 3. Schedule +1 Week  
**Purpose:** Quality of life / schedule navigation

This extension is a schedule navigation shortcut.

It takes the current Jane schedule URL, moves the date forward by 7 days, and removes staff filters from the URL. If the original URL contains `/shifts/`, that part is preserved.

This is useful for quickly jumping to the same schedule view for the next week without manually changing the date or clearing staff IDs.

#### What it does
- Reads the current schedule date from the URL
- Adds 7 days
- Removes all staff IDs from the URL
- Preserves `/shifts/` if it exists in the original URL

#### Examples

From:

`https://vcmt.janeapp.com/admin#schedule/staff/1782-1783-1784/2026-06-29`

To:

`https://vcmt.janeapp.com/admin#schedule/2026-07-06`

From:

`https://vcmt.janeapp.com/admin#schedule/staff/1782-1783-1784/shifts/2026-06-29`

To:

`https://vcmt.janeapp.com/admin#schedule/shifts/2026-07-06`

#### Use case
Use this when working in the Jane schedule and you want to jump forward one week while clearing staff-specific filters.

#### How to use
1. Open a Jane schedule page
2. Click the extension button
3. The extension will:
   - move the date forward by one week
   - remove staff IDs
   - preserve `shifts` mode if present

---

### Installing the JaneApp extensions

These extensions are intended to be loaded manually in a Chromium-based browser such as Chrome or Edge.

1. Download or clone this repository
2. Open `chrome://extensions` or `edge://extensions`
3. Enable **Developer mode**
4. Click **Load unpacked**
5. Select the folder for the extension you want to use

If you update one of the extension files:
1. Save the file
2. Return to the extensions page
3. Click **Reload**
4. Refresh the JaneApp tab before testing again

---

## CMTCA Shift Checker

This is a script that takes JSON file(s) containing a cohort’s schedule(s) from SAZED and outputs a spreadsheet showing which shifts each cohort member attended, along with a count of how many times each shift was attended.

### Requirements
- Python
- Pandas

### Usage
1. Create a folder named `data` in the same directory as the script
2. Go to the **Schedule** tab of SAZED
3. Open the Developer Console in your browser and go to the **Network** tab
4. Clear the current output inside the Network tab
5. Choose the cohort and semester you want
6. Look for a request named `GetShiftsByCohort`
7. Copy the response of that request to a JSON file inside the `data` folder
8. Repeat steps 5–7 as needed
9. Run the script

### Output
The script generates a spreadsheet showing:
- which shifts each cohort member attended
- how many times each shift was attended

---

## Student File Checker

This script browses all of the clinic’s student permanent record folders and generates an HTML report showing which students are missing which files.

The report also provides a direct button or link to each student’s folder for easier access and follow-up.

### Purpose
Use this to quickly identify missing documents in student permanent records without manually checking every folder one by one.

### Output
The script generates an HTML report that:
- lists students with missing files
- shows which files are missing
- includes a direct link or button to open the relevant folder

---

## Notes

- These tools are built for internal VCMT workflows
- Some scripts depend on current third-party site behavior and may require updates over time
- Use care with any automation that clicks buttons or saves changes automatically
- Review outputs before relying on them for final administrative decisions

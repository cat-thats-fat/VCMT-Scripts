#Student File Checker
#Purpose: To check the student permanent records for the presence of the required clinic files.
#Last Updated: 2025-03-23

import re
import datetime
import webbrowser
from pathlib import Path

def htmlReport(problems, student_count, item_count, problem_count, time_taken):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Student File Records Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        .summary {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .class {{ margin-bottom: 30px; border-left: 5px solid #3498db; padding-left: 15px; }}
        .student {{ margin: 10px 0; padding: 10px; background-color: #f1f1f1; border-radius: 3px; }}
        .missing {{ color: #e74c3c; }}
        .good {{ color: #27ae60; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .folder-link {{ background-color: #3498db; color: white; padding: 5px 10px; 
                       text-decoration: none; border-radius: 3px; display: inline-block; }}
        .folder-link:hover {{ background-color: #2980b9; }}
    </style>
</head>
<body>
    <h1>Student File Checker Report</h1>
    <div class="summary">
        <p><strong>Total students checked:</strong> {student_count}</p>
        <p><strong>Total items checked:</strong> {item_count}</p>
        <p><strong>Total problems found:</strong> {problem_count}</p>
        <p><strong>Time taken:</strong> {time_taken}</p>
        <p><strong>Report generated:</strong> {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
"""

    # Add each class section
    for class_name, students in problems.items():
        if not students:  # Skip classes with no problems
            continue
            
        html += f'<div class="class">\n<h2>{class_name}</h2>\n'
        
        # Create a table for this class's students
        html += """<table>
    <tr>
        <th>Student Name</th>
        <th>First Aid</th>
        <th>Expected Contracts</th>
        <th>Actual Contracts</th>
        <th>Missing Files</th>
        <th>Actions</th>
    </tr>
"""
        
        # Add each student's row
        for student_name, details in students.items():
            html += f'<tr>\n<td>{student_name}</td>\n'
            
            # First Aid status
            if details.get("hasFirstAid", False):
                html += '<td class="good">Yes</td>\n'
            else:
                html += '<td class="missing">No</td>\n'
                
            # Expected and actual contract count
            html += f'<td>{details.get("expectedContractCount", "Unknown")}</td>\n'
            html += f'<td>{details.get("actualContractCount", 0)}</td>\n'
            
            # Missing files
            missing_files = details.get("missingFiles", [])
            if missing_files:
                html += '<td class="missing">' + ', '.join(missing_files) + '</td>\n'
            else:
                html += '<td>None</td>\n'
                
            # Link to student folder
            path = details.get("path")
            if path:
                html += f'<td><a href="{path}" class="folder-link">Open Folder</a></td>\n'
            else:
                html += '<td>N/A</td>\n'
                
            html += '</tr>\n'
            
        html += '</table>\n</div>\n'
    
    html += """</body>
</html>"""
    
    # Write the HTML file
    report_path = "recordReport.html"
    with open(report_path, "w") as f:
        f.write(html)
    
    return report_path

#Initialize variables

#Dictionary to store problematic student folders
problems = {}
#Count of problematic student folders
problemCount = 0
#Count of students checked
studentCount = 0
#Count of items checked
itemCount = 0
#Time at start of script
startTime = datetime.datetime.now()

#Dictionary that holds the required files and their regex(search key) patterns
requiredFiles = {
    "First Aid": r"First Aid",
    "Clinic Contract": r"VCMT Clinic Internship Contract"
    # old regex "\w+\s\w+\sVCMT\sClinic\sInternship\sContract\s-\s20[\d][\d]\s(Summer|Fall|Winter)"
}

#compile patterns
patterns = {key: re.compile(pattern) for key, pattern in requiredFiles.items()}

#Dictionary for the semesters and their corresponding month ranges
# Value format: [startin month, ending month]
semesterRanges = {
    "Winter": [1, 4],
    "Summer": [5, 8],
    "Fall": [9, 12]
}

#T:\STUDENTS\STUDENT PERMANENT RECORDS
#C:\Users\declan\Documents\Coding\SFC\STUDENT PERMANENT RECORDS

#Path to the perm records directory
rootDir = r"T:\STUDENTS\STUDENT PERMANENT RECORDS"
rootPath = Path(rootDir)

#Get current Semester
currentMonth = datetime.datetime.now().month
currentSem = next(
    semester for semester, (start, end) in semesterRanges.items()
    if start <= currentMonth <= end
)

#iterating through all classes
for classDir in rootPath.iterdir():
    print(f"Checking {classDir.name}.")
    #skip file if not a directory
    if not classDir.is_dir() or re.search(r"^\d{4}\s\d(?:Summer|Fall|Winter)\s(?:FT|PT)\s-\s.*$", classDir.name) == None:
        print(f"Skipping {classDir.name}: \n\t Incorrect formatting.")
        continue

    #extracting class info from the class directory name
    currentClassArray = classDir.name.split(maxsplit=4)
    currentClassStartYear = currentClassArray[0]
    currentClassStartSem = currentClassArray[1][1:]
    currentClassProgram = currentClassArray[2]

    # Calculate how many semesters the cohort has been in clinic
    currentSemStart = datetime.datetime.strptime(f"{datetime.datetime.now().year}-{semesterRanges[currentSem][0]}", "%Y-%m")
    currentClassStartDate = datetime.datetime.strptime(f"{currentClassStartYear}-{semesterRanges[currentClassStartSem][0]}", "%Y-%m")
    semSinceStart = ((currentSemStart.year - currentClassStartDate.year) * 12 + (currentSemStart.month - currentClassStartDate.month))/4 + 1

    # Skip if the class is not currently in clinic
    if (currentClassProgram == "PT" and (semSinceStart > 6 or semSinceStart < 3)) or (currentClassProgram == "FT" and (semSinceStart > 5 or semSinceStart < 2)):
        print(f"Skipping {classDir.name}: \n\t Not currently in clinic.")
        continue

    if currentClassProgram == "PT":
        expectedContractCount =  semSinceStart - 2
    elif currentClassProgram == "FT":
        expectedContractCount =  semSinceStart - 1
    currentClassName = currentClassArray[4]

    if currentClassName not in problems:
        problems[currentClassName] = {}

    # studentDir is a student's folder
    for studentDir in classDir.iterdir():
        print(f"Checking {studentDir.name}.")
        if not studentDir.is_dir():
            print(f"Skipping {studentDir.name}: \n\t Not a directory.")
            continue

        contractCount = 0
        firstAid = False
        clinicDir = studentDir / "Clinic"
        if not clinicDir.exists():
            print(f"Skipping {studentDir.name}: \n\t Incorrect directory format.")
            continue
        studentCount += 1

       # item is file in a student folder
        for item in clinicDir.iterdir():
           for fileType, pattern in patterns.items():
                if re.search(pattern, item.name):
                    if fileType == "First Aid":
                        firstAid = True
                    elif fileType == "Clinic Contract":
                        contractCount += 1
        itemCount += 1

        if contractCount != expectedContractCount or not firstAid:
            problemCount += 1
            # Store problem details with path for HTML report
            problems[currentClassName][studentDir.name] = {
                "expectedContractCount": expectedContractCount,
                "actualContractCount": contractCount,
                "hasFirstAid": firstAid,
                "path": clinicDir.as_uri(),  # Store the URI for the HTML link
                "missingFiles": []
            }
            
            # Add details about what's missing
            if not firstAid:
                problems[currentClassName][studentDir.name]["missingFiles"].append("First Aid")
            if contractCount != expectedContractCount:
                problems[currentClassName][studentDir.name]["missingFiles"].append(
                    f"{abs(int(expectedContractCount - contractCount))} Clinic Contract(s)"
                )

print("\nStudent File Checker Complete.")
print(f"Total students checked: {studentCount}")
print(f"Total items checked: {itemCount}")
print(f"Total problems found: {problemCount}")
print(f"Time taken: {datetime.datetime.now() - startTime}")

# Generate HTML report and open in browser
time_taken = datetime.datetime.now() - startTime
report_path = htmlReport(problems, studentCount, itemCount, problemCount, time_taken)
print(f"HTML report saved to {report_path}")

# Ask if user wants to open the report
open_report = input("Open HTML report now? (y/n): ")
if open_report.lower() == 'y':
    webbrowser.open(report_path)
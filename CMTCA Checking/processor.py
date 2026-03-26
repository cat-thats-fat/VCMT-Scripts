import os
import json
import pandas as pd
from datetime import datetime

def processor(wdir):
    # Initialize an empty DataFrame
    schedules_df = pd.DataFrame()

    schedules = os.listdir(f"{wdir}/data")

    # Iterate over schedules
    for schedule in schedules:
        with open(f"./data/{schedule}", "r") as f:
            rawdata = json.load(f)

        studentDict = rawdata["queryData"]["data"]["studentCohortShifts"]

        # Process each student and their shifts

        excluededShiftTypes = [
                "ADMIN AM",
                "ADMIN PM",
                "Sat ADMIN AM",
                "Sat ADMIN PM",
                "CAD",
                "CAD #1",
                "CAD #2",
                "CAD #3",
                "CS",
                "Orientation",
                "MOCK CLINIC",
                "WW F",
                "WW S/S",
                "STAT"
                #"Mentor",
                #"ICORD Tour",
        ]

        rows = []
        shiftArray = []
        for student_key, stdSchedule in studentDict.items():
            # Extract the name part from the student key
            student_name = student_key.split(" - ")[0]
            for shifts in stdSchedule.values():
                    for shift in shifts:
                        shiftType = shift["type"]["name"]

                        if shiftType not in shiftArray:
                            shiftArray.append(shiftType)

                        absence = shift["absence"]
                        if absence is None and not shiftType in excluededShiftTypes:
                            # Use the cleaned student name
                            rows.append([student_name, shift["type"]["name"]])

        # Append to the DataFrame
        temp_df = pd.DataFrame(rows, columns=["Student", "Shift Type"])
        schedules_df = pd.concat([schedules_df, temp_df], ignore_index=True)

    # Pivot the DataFrame to get the desired format
    pivot_df = schedules_df.pivot_table(index="Student", columns="Shift Type", aggfunc="size", fill_value=0)

    # Add a sum column for each student
    pivot_df["Total"] = pivot_df.sum(axis=1)

    # Reset the index to include "Student" as a column
    pivot_df.reset_index(inplace=True)

    # Reorder columns to make "Total" the second column
    columns = ["Student", "Total"] + [col for col in pivot_df.columns if col not in ["Student", "Total"]]
    pivot_df = pivot_df[columns]

    # Save the DataFrame to an Excel file
    pivot_df.to_excel("schedules_output.xlsx", index=False)
    print("Schedules exported to schedules_output.xlsx")
    print(shiftArray)



def prettifier(wdir):
    schedules = os.listdir(f"{wdir}/rawjson/")

    for schedule in schedules:
        infile = f"{wdir}/rawjson/{schedule}"
        outfile = f"{wdir}/data/{schedule}.json"

        with open(infile, "r") as f:
            parsed = json.load(f)

        # Save pretty-printed JSON
        with open(outfile, "w") as f:
            json.dump(parsed, f, indent=4)

def main():
    wdir = os.getcwd()

    prettifier(wdir)

    processor(wdir)

if __name__ == "__main__":
    main()
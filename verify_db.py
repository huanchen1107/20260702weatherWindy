import sqlite3
import csv
import sys

def verify():
    # Force output encoding to utf-8 for terminal print if needed
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass # Older Python versions
            
    print("=== VERIFYING DATABASE CONTENTS ===")
    conn = sqlite3.connect("weather.db")
    cursor = conn.cursor()
    cursor.execute("SELECT station_name, county_name, weather FROM weather LIMIT 10")
    db_rows = cursor.fetchall()
    for row in db_rows:
        print(f"Station: {row[0]}, County: {row[1]}, Weather: {row[2]}")
    conn.close()

    print("\n=== VERIFYING CSV CONTENTS ===")
    with open("weather.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        print("Header:", header[:5])
        for idx, row in enumerate(reader):
            if idx < 5:
                print(f"Row {idx+1}: {row[0]}, {row[1]}, {row[2]}, {row[3]}, {row[4]}, {row[6]}")
            else:
                break

if __name__ == "__main__":
    verify()

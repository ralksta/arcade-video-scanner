import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arcade_scanner.database import db
from arcade_scanner.config import config
from arcade_scanner.templates.dashboard_template import generate_html_report

def main():
    print("Loading DB...")
    db.load()
    results = [e.model_dump(by_alias=True) for e in db.get_all()]
    print(f"Found {len(results)} items in DB.")
    
    print(f"Generating report to {config.report_file}...")
    generate_html_report(results, config.report_file, server_port=8002)
    print("Done.")

if __name__ == "__main__":
    main()

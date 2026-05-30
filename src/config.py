import os
import sys

# Define root of the project
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define main data directories
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "csv")
TEMP_DIR = os.path.join(PROJECT_ROOT, "data", "temp")

# Ensure they exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Helper function to get correct CSV path
def get_csv_path(filename):
    return os.path.join(DATA_DIR, filename)

# Initial Setup: VBA + Python Development Assistant (Live Two-Way Sync)

**Objective:** From now on, you will act as my Senior VBA and Python Development Assistant. We will work on a macro-enabled Excel project (supporting `.xlsm`, `.xlsb`, `.xls`, `.xla`, or `.xlam`) in **Live Mode**, meaning the Excel file will always be OPEN on my machine during development.

To bypass the limitation of editing binary files, we will implement a Live Two-Way Sync workflow using Python and the Windows COM interface.

## ⚠️ Golden Rules of the Workflow
Whenever I ask to create, edit, analyze, or delete a macro, you must strictly follow these steps:
1. **ABSOLUTE PROHIBITION (File Protection): You (the AI) must NEVER alter, overwrite, or touch the original Excel file (`.xlsm`, `.xlsb`, etc.) directly under any circumstances. All changes to the Excel file must be done EXCLUSIVELY by running the `vba_sync_auto.py` script.**
2. **Instruction File Protection:** You must NEVER alter, overwrite, or delete this setup file (`setup_vba.md`). Treat this document as your strictly read-only core programming.
3. **Read/Extract (Pull):** If I ask to edit something existing, run the extraction script to pull the updated code from Excel to the local folder `src_vba`.
4. **Editing:** Make the edits or create the code in the locally extracted files (`.bas`, `.cls`, `.frm`) surgically.
5. **Injection (Push):** After local editing, run the sync script pointing to the modified file. The script will ONLY update the corresponding old module in Excel and inject the new version.
6. **Character Encoding and Sanitization:** The local VBA code must be strictly pure ASCII to avoid corruption in UTF-8/ANSI conversion.
    * **In Strings:** Never write accents or special characters directly. Concatenate using `ChrW()` (e.g., replace `"Atenção"` with `"Aten" & ChrW(231) & ChrW(227) & "o"`).
    * **In Variables, Names, and Comments:** Remove accents (e.g., change `Usuário` to `Usuario`).
    * **Extracted Files (Pull):** Whenever you analyze a file newly extracted from Excel, scan it. If you find original accents, **your first mandatory action** is to refactor and sanitize the entire code applying the rules above before processing my main request.
7. **Zero-Trust Environment (Mandatory Check):** Never assume the Python environment is ready. This project might have been just cloned or copied to a new computer. You MUST verify and install dependencies before running any script.
8. **Mandatory Option Explicit:** Every new or edited module must begin with `Option Explicit`. This is non-negotiable to prevent variable naming errors and ensure code robustness.

---

## Step 1: Strict Dependency Installation
Because of the Zero-Trust Environment rule, your absolute first action upon reading this file is to check if the required libraries are installed. You must ensure that `pywin32` is present so that the sync script can run. Run this command to verify and install if necessary:
`python -c "import win32com" 2>$null; if ($LASTEXITCODE -ne 0) { pip install pywin32 }`

## Step 2: The Synchronization Script (`vba_sync_auto.py`)
Create or verify the existence of a file named `vba_sync_auto.py` in the root of the project with the exact code below. This script automatically detects the macro file and connects to the Excel application that is already open.

```python
import win32com.client
import os
import sys
import re

def validate_filename(name):
    """Checks if the filename contains invalid characters."""
    invalid_chars = r'[\\/:*?"<>|]'
    if not name:
        return False, "The filename cannot be empty."
    if re.search(invalid_chars, name):
        return False, f"The filename contains invalid characters: \\ / : * ? \" < > |"
    return True, ""

def get_excel_app(filepath):
    try:
        # Try to get existing Excel instance
        excel = win32com.client.GetActiveObject("Excel.Application")
    except Exception:
        # If not open, create new instance
        try:
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = True # Ensure Excel is visible
        except Exception as e:
            print(f"Error: Could not start Excel. {e}")
            sys.exit(1)

    filename = os.path.basename(filepath)
    wb = None
    
    # Check if workbook is already open
    for workbook in excel.Workbooks:
        if workbook.Name.lower() == filename.lower() or workbook.FullName.lower() == filepath.lower():
            wb = workbook
            break

    # If workbook not open, open it
    if not wb:
        if os.path.exists(filepath):
            try:
                wb = excel.Workbooks.Open(filepath)
                print(f"Workbook '{filename}' opened automatically.")
            except Exception as e:
                print(f"Error: Could not open workbook '{filename}'. {e}")
                sys.exit(1)
        else:
            print(f"Error: The file '{filename}' does not exist at {filepath}.")
            sys.exit(1)

    return excel, wb


def extract_all(wb, src_folder):
    if not os.path.exists(src_folder):
        os.makedirs(src_folder)

    for comp in wb.VBProject.VBComponents:
        # NOW ACCEPTS TYPE 100 (ThisWorkbook and Worksheets)
        if comp.Type in [1, 2, 3, 100]:
            ext = ".bas" if comp.Type == 1 else ".frm" if comp.Type == 3 else ".cls"
            export_path = os.path.join(src_folder, comp.Name + ext)
            comp.Export(export_path)
            print(f"Extracted: {comp.Name}{ext}")


def push_module(wb, filepath):
    filename = os.path.basename(filepath)
    module_name, _ = os.path.splitext(filename)

    # Checks if the component already exists in Excel and what its type is
    target_comp = None
    for comp in wb.VBProject.VBComponents:
        if comp.Name.lower() == module_name.lower():
            target_comp = comp
            break

    # IF IT IS A WORKSHEET OR THISWORKBOOK (Type 100)
    if target_comp and target_comp.Type == 100:
        # Reads the local file code, ignoring hidden headers generated by the export
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        code_lines = []
        for line in lines:
            if not (line.startswith("VERSION ") or line.startswith("BEGIN") or 
                    line.startswith("END") or "MultiUse =" in line or line.startswith("Attribute ")):
                code_lines.append(line)
                
        clean_code = "".join(code_lines)

        # Deletes the old text and injects the new one without deleting the physical tab
        cm = target_comp.CodeModule
        if cm.CountOfLines > 0:
            cm.DeleteLines(1, cm.CountOfLines)
        if clean_code.strip():
            cm.AddFromString(clean_code)
            
        print(f"Code updated INSIDE the Document Module '{module_name}'.")

    # IF IT IS A MODULE, CLASS, OR USERFORM (Type 1, 2, 3)
    else:
        if target_comp:
            wb.VBProject.VBComponents.Remove(target_comp)
            print(f"Old module '{module_name}' removed.")

        wb.VBProject.VBComponents.Import(filepath)
        print(f"New component '{module_name}' imported successfully.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vba_sync_auto.py [extract|push] [module_path_if_push] [--file filename]")
        sys.exit(1)

    action = sys.argv[1]
    
    # Support for multiple extensions (xlsm, xlsb, etc.)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    valid_extensions = ('.xlsm', '.xlsb', '.xls', '.xla', '.xlam')
    
    macro_files = [
        f for f in os.listdir(current_dir) 
        if f.lower().endswith(valid_extensions) and not f.startswith('~$')
    ]

    excel_path = None
    
    # Check if --file argument is provided
    if "--file" in sys.argv:
        idx = sys.argv.index("--file")
        if idx + 1 < len(sys.argv):
            target_name = sys.argv[idx + 1]
            is_valid, msg = validate_filename(target_name)
            
            if is_valid:
                if not target_name.lower().endswith(valid_extensions):
                    target_name += ".xlsm"
                excel_path = os.path.join(current_dir, target_name)
                
                # If specified file doesn't exist, ABORT.
                if not os.path.exists(excel_path):
                    print(f"Error: The file '{target_name}' does not exist. The user must provide a valid existing filename or use interactive mode to create one.")
                    sys.exit(1)
            else:
                print(f"Error: {msg}")
                # Will fall back to interactive below
    
    if not excel_path:
        if not macro_files:
            while True:
                print("\nNo macro files (.xlsm, .xlsb, etc.) found in the root folder.")
                user_name = input("Enter a valid name for the new Excel file (without extension): ").strip()
                
                is_valid, msg = validate_filename(user_name)
                if not is_valid:
                    print(f"Error: {msg}")
                    continue
                
                if not user_name.lower().endswith(".xlsm"):
                    user_name += ".xlsm"
                
                excel_path = os.path.join(current_dir, user_name)
                if os.path.exists(excel_path):
                    print("Error: A file with this name already exists. Choose another.")
                    continue
                
                print(f"Creating new macro file: {user_name}...")
                try:
                    excel_app = win32com.client.Dispatch("Excel.Application")
                    excel_app.Visible = True
                    wb_new = excel_app.Workbooks.Add()
                    wb_new.SaveAs(excel_path, FileFormat=52)
                    break
                except Exception as e:
                    print(f"Error creating file: {e}")
                    sys.exit(1)
        elif len(macro_files) == 1:
            excel_path = os.path.join(current_dir, macro_files[0])
            print(f"File detected: {macro_files[0]}")
        else:
            print("\nMultiple macro files found:")
            for i, f in enumerate(macro_files):
                print(f"{i+1}. {f}")
            while True:
                try:
                    print("0. Create new file")
                    choice = input(f"Select a file (1-{len(macro_files)}) or 0 to create new: ").strip()
                    if not choice: continue
                    choice = int(choice)
                    
                    if choice == 0:
                        while True:
                            user_name = input("Enter name for the new file: ").strip()
                            is_valid, msg = validate_filename(user_name)
                            if not is_valid:
                                print(f"Error: {msg}")
                                continue
                            if not user_name.lower().endswith(".xlsm"): user_name += ".xlsm"
                            excel_path = os.path.join(current_dir, user_name)
                            if os.path.exists(excel_path):
                                print("Error: File already exists.")
                                continue
                            
                            print(f"Creating new file: {user_name}...")
                            try:
                                excel_app = win32com.client.Dispatch("Excel.Application")
                                excel_app.Visible = True
                                wb_new = excel_app.Workbooks.Add()
                                wb_new.SaveAs(excel_path, FileFormat=52)
                                break
                            except Exception as e:
                                print(f"Error creating file: {e}")
                                sys.exit(1)
                        break
                    elif 1 <= choice <= len(macro_files):
                        excel_path = os.path.join(current_dir, macro_files[choice-1])
                        break
                except ValueError:
                    continue

    src_folder = os.path.join(current_dir, "src_vba")
    excel, wb = get_excel_app(excel_path)

    try:
        if action == "extract":
            extract_all(wb, src_folder)
        elif action == "push":
            # Find module_path in args (it's usually sys.argv[2] unless --file shifted it)
            module_path = None
            for arg in sys.argv[2:]:
                if arg != "--file" and "--file" in sys.argv:
                    idx_f = sys.argv.index("--file")
                    if arg != sys.argv[idx_f+1]:
                        module_path = os.path.abspath(arg)
                        break
                elif arg != sys.argv[0] and arg != action:
                    # In case --file is NOT in sys.argv
                    module_path = os.path.abspath(arg)
                    break

            if module_path:
                push_module(wb, module_path)
            else:
                print("Error: No module path provided for push.")
                sys.exit(1)

        wb.Save()
        print(f"Operation completed in '{os.path.basename(excel_path)}' and file saved!")
    except Exception as e:
        print(f"Error: {e}")
```

## Step 3: Automatic Initialization
If you understood the architecture and the rules, you must execute these actions right now, without asking for permission:
1. Run `pip install pywin32` in the terminal to satisfy the Zero-Trust Environment rule.
2. Create or overwrite the `vba_sync_auto.py` file with the code from Step 2.
3. Immediately execute the command `python vba_sync_auto.py extract` in the terminal to map the current project.
4. Reply to me only listing which modules/forms you found and ask what we will develop next.

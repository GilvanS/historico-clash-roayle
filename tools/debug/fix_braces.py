import re

file_path = 'src/html_generator.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the region to fix
start_marker = "    function switchAccountTab(tag, element) {"
end_marker = "            if (!dayBtn) {\n                dayBtn = calendarEl.querySelector('.rd-calendar-day');\n            }}"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker) + len(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers")
    exit(1)

text_to_fix = content[start_idx:end_idx]

# Replace { with {{ and } with }}
text_fixed = text_to_fix.replace('{', '{{').replace('}', '}}')

# Careful: if the original text_to_fix had any {{ or }} inside, they became {{{{ and }}}}.
# We can just replace {{{{ with {{ and }}}} with }}
text_fixed = text_fixed.replace('{{{{', '{{').replace('}}}}', '}}')

new_content = content[:start_idx] + text_fixed + content[end_idx:]

# Also fix the line we left with single braces:
# selectWarDay(tabId, date, dayBtn, true);
# Wait, let's just make sure we fix:
#             if (dayBtn) {{
#                 var date = dayBtn.getAttribute('data-date');
#                 selectWarDay(tabId, date, dayBtn);
#             }}
new_content = new_content.replace(
    "            if (dayBtn) {{\n                var date = dayBtn.getAttribute('data-date');\n                selectWarDay(tabId, date, dayBtn);\n            }}",
    "            if (dayBtn) {{\n                var date = dayBtn.getAttribute('data-date');\n                selectWarDay(tabId, date, dayBtn, true);\n            }}"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Fixed braces!")

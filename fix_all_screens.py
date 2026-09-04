#!/usr/bin/env python3
import re
import os

files_to_fix = [
    r"D:\Pranav\app\ui\login_screen.py",
    r"D:\Pranav\app\ui\dialogs\account_metadata_dialog.py",
    r"D:\Pranav\app\ui\income_management_screen.py",
    r"D:\Pranav\app\ui\widgets\summary_panel.py",
    r"D:\Pranav\app\ui\fixed_deposits_screen.py",
    r"D:\Pranav\app\ui\statement_import_screen_modern.py",
    r"D:\Pranav\app\ui\settings_screen.py",
    r"D:\Pranav\app\ui\transactions_screen.py",
    r"D:\Pranav\app\ui\ais_tis_import_screen_v2.py",
    r"D:\Pranav\app\ui\dialogs\password_dialog.py",
]

for file_path in files_to_fix:
    if not os.path.exists(file_path):
        continue

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip())
        var_match = re.search(r'(\w+)\.setStyleSheet', line)
        var_name = var_match.group(1) if var_match else None

        # Handle Title styles
        if 'Theme.title_style(18)' in line:
            line = line.replace('Theme.title_style(18)', '"textrole", "title-xl")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.title_style(16)' in line:
            line = line.replace('Theme.title_style(16)', '"textrole", "title-lg")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.title_style(15)' in line:
            line = line.replace('Theme.title_style(15)', '"textrole", "title-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.title_style(14)' in line:
            line = line.replace('Theme.title_style(14)', '"textrole", "title-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')

        # Handle Muted styles
        elif 'Theme.muted_style(11)' in line:
            line = line.replace('Theme.muted_style(11)', '"textrole", "muted-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.muted_style(12)' in line:
            line = line.replace('Theme.muted_style(12)', '"textrole", "muted-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')

        # Handle Section label styles
        elif 'Theme.section_label_style()' in line or 'Theme.section_label_style(12)' in line:
            line = line.replace('Theme.section_label_style()', '"textrole", "section-label")')
            line = line.replace('Theme.section_label_style(12)', '"textrole", "section-label")')
            line = line.replace('.setStyleSheet(', '.setProperty(')

        # Handle common text styles - long ones first
        elif 'Theme.text_style(color=Theme.TEXT_SECONDARY, size=12, weight=600)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_SECONDARY, size=12, weight=600)', '"textrole", "emphasis-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_SECONDARY, size=13)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_SECONDARY, size=13)', '"textrole", "secondary-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_SECONDARY, size=12)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_SECONDARY, size=12)', '"textrole", "secondary-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_MUTED, size=12)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_MUTED, size=12)', '"textrole", "muted-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_MUTED, size=11)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_MUTED, size=11)', '"textrole", "muted-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=700)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=700)', '"textrole", "emphasis-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_PRIMARY, size=14, weight=700)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_PRIMARY, size=14, weight=700)', '"textrole", "emphasis-lg")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=700)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=700)', '"textrole", "emphasis-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=600)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_PRIMARY, size=11, weight=600)', '"textrole", "emphasis-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=600)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_PRIMARY, size=13, weight=600)', '"textrole", "emphasis-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_PRIMARY, size=12, weight=700)', '"textrole", "emphasis-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.TEXT_PRIMARY, size=13)' in line:
            line = line.replace('Theme.text_style(color=Theme.TEXT_PRIMARY, size=13)', '"textrole", "body-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(size=13)' in line:
            line = line.replace('Theme.text_style(size=13)', '"textrole", "body-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(size=12)' in line:
            line = line.replace('Theme.text_style(size=12)', '"textrole", "body-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(size=11)' in line:
            line = line.replace('Theme.text_style(size=11)', '"textrole", "muted-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
        elif 'Theme.text_style(color=Theme.INFO_DARK, size=13)' in line:
            line = line.replace('Theme.text_style(color=Theme.INFO_DARK, size=13)', '"textrole", "body-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
            output.append(line)
            if var_name:
                output.append(' ' * indent + f'{var_name}.setProperty("color", "info")\n')
            i += 1
            continue
        elif 'Theme.text_style(color=Theme.WARNING_DARK, size=12, weight=600)' in line:
            line = line.replace('Theme.text_style(color=Theme.WARNING_DARK, size=12, weight=600)', '"textrole", "emphasis-sm")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
            output.append(line)
            if var_name:
                output.append(' ' * indent + f'{var_name}.setProperty("color", "warning")\n')
            i += 1
            continue
        elif 'Theme.text_style(color=Theme.DANGER_DARK, size=13)' in line:
            line = line.replace('Theme.text_style(color=Theme.DANGER_DARK, size=13)', '"textrole", "body-md")')
            line = line.replace('.setStyleSheet(', '.setProperty(')
            output.append(line)
            if var_name:
                output.append(' ' * indent + f'{var_name}.setProperty("color", "danger")\n')
            i += 1
            continue

        output.append(line)
        i += 1

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(output)
    print(f"Fixed {file_path}")

print("Done fixing all eligible files")

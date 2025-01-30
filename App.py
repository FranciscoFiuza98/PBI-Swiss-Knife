import os
import re
import json
import streamlit as st
from pathlib import Path

def load_semantic_model(folder_path):
    """Load and validate semantic model folder structure."""
    folder = Path(folder_path)
    definition_path = folder / "definition"
    model_path = definition_path / "model.tmdl"
    
    if not folder.exists():
        return None, "Selected folder does not exist"
    if not definition_path.exists():
        return None, "definition folder not found in semantic model"
    if not model_path.exists():
        return None, "model.tmdl not found in definition folder"
        
    return model_path, None

class RuleChecker:
    def __init__(self, model_path):
        self.model_path = Path(model_path)
        self.model_dir = self.model_path.parent
        self.content = None
        self.table_files = []
        self.load_content()
        
    def load_content(self):
        """Load the model.tmdl content and find all table files."""
        try:
            # Load main model file
            with open(self.model_path, "r", encoding='utf-8') as f:
                self.content = f.read()
            
            # Find all .tmdl files in tables directory
            tables_dir = self.model_dir / "tables"
            if tables_dir.exists():
                self.table_files = list(tables_dir.glob("*.tmdl"))
                
        except Exception as e:
            st.error(f"Error loading model files: {str(e)}")
            self.content = None
            
    def check_uppercase_first_letter_measures_tables(self):
        """Check for violations of the UPPERCASE_FIRST_LETTER_MEASURES_TABLES rule."""
        if not self.content:
            return None
            
        violations = []
        
        def check_tables_in_content(content, file_path):
            # Look for unquoted table definitions (table TableName)
            table_matches = re.finditer(r'(?m)^table\s+([a-zA-Z][a-zA-Z0-9_]*?)(?:\s*$|\s+(?:lineageTag|dataCategory))', content)
            for match in table_matches:
                table_name = match.group(1)
                if table_name[0].islower():
                    violations.append({
                        'type': 'table',
                        'name': table_name,
                        'line': content.count('\n', 0, match.start()) + 1,
                        'file': file_path
                    })
            
            # Look for quoted table definitions (table 'TableName')
            quoted_table_matches = re.finditer(r"(?m)^table\s+'([^']+?)'(?:\s*$|\s*=|\s+(?:lineageTag|dataCategory))", content)
            for match in quoted_table_matches:
                table_name = match.group(1)
                if table_name[0].islower():
                    violations.append({
                        'type': 'calculated table',
                        'name': table_name,
                        'line': content.count('\n', 0, match.start()) + 1,
                        'file': file_path
                    })
        
        # Check tables in all files
        files_to_check = [self.model_path] + self.table_files
        for file_path in files_to_check:
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    content = f.read()
                
                # Check for table definitions
                check_tables_in_content(content, file_path)
                
                # Look for measure definitions (measure 'MeasureName' = )
                measure_matches = re.finditer(r"(?m)^\s*measure\s+'([^']+?)'(?:\s*=|$)", content)
                for match in measure_matches:
                    measure_name = match.group(1)
                    # Only add if the first letter is lowercase
                    if measure_name[0].islower():
                        violations.append({
                            'type': 'measure',
                            'name': measure_name,
                            'line': content.count('\n', 0, match.start()) + 1,
                            'file': file_path
                        })
                    
            except Exception as e:
                st.warning(f"Error checking file {file_path}: {str(e)}")
                continue
            
        return violations if violations else None
        
    def fix_uppercase_first_letter(self, violations):
        """Fix violations of the UPPERCASE_FIRST_LETTER_MEASURES_TABLES rule."""
        try:
            # Group violations by file
            violations_by_file = {}
            for violation in violations:
                file_path = Path(violation['file'])
                if file_path not in violations_by_file:
                    violations_by_file[file_path] = []
                violations_by_file[file_path].append(violation)
            
            # Fix violations in each file
            for file_path, file_violations in violations_by_file.items():
                with open(file_path, "r", encoding='utf-8') as f:
                    content = f.read()
                
                # Fix each violation
                for violation in file_violations:
                    old_name = violation['name']
                    new_name = old_name[0].upper() + old_name[1:]
                    
                    if violation['type'] == 'table' and not old_name.startswith("'"):
                        # For unquoted table names
                        pattern = f"table {re.escape(old_name)}\\b"
                        content = re.sub(pattern, f"table {new_name}", content)
                    else:
                        # For measures and quoted table names
                        pattern = f"'({re.escape(old_name)})'"
                        content = re.sub(pattern, lambda m: f"'{new_name}'", content)
                
                # Write the fixed content back
                with open(file_path, "w", encoding='utf-8') as f:
                    f.write(content)
            
            # Reload content after all fixes
            self.load_content()
            return None
            
        except Exception as e:
            st.error(f"Error fixing uppercase first letter rule: {str(e)}")
            return str(e)

    def check_no_pascalcase_columns_hierarchies(self):
        """Check for PascalCase usage in visible columns and hierarchies."""
        if not self.content:
            return None
            
        violations = []
        
        # Pattern to match PascalCase (at least two capital letters with lowercase in between)
        pascal_pattern = r"[A-Z]([A-Z0-9]*[a-z][a-z0-9]*[A-Z]|[a-z0-9]*[A-Z][A-Z0-9]*[a-z])[A-Za-z0-9]*"
        
        def is_pascalcase_without_spaces(name):
            """Check if a name is in PascalCase and doesn't contain spaces."""
            return bool(re.match(pascal_pattern, name)) and ' ' not in name
        
        # Check all files for columns and hierarchies
        files_to_check = [self.model_path] + self.table_files
        for file_path in files_to_check:
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    content = f.read()
                
                # Look for column definitions
                column_types = ['column', 'calculatedColumn', 'dataColumn', 'calculatedTableColumn']
                for col_type in column_types:
                    # Match column definitions that don't have isHidden = true
                    column_matches = re.finditer(
                        rf"(?m)^\s*{col_type}\s+([A-Za-z][A-Za-z0-9_]*)\b(?:(?!isHidden\s*=\s*true).)*$",
                        content,
                        re.DOTALL
                    )
                    
                    for match in column_matches:
                        col_name = match.group(1)
                        if is_pascalcase_without_spaces(col_name):
                            violations.append({
                                'type': col_type,
                                'name': col_name,
                                'line': content.count('\n', 0, match.start()) + 1,
                                'file': file_path
                            })
                
                # Look for hierarchy definitions
                hierarchy_matches = re.finditer(
                    r"(?m)^\s*hierarchy\s+([A-Za-z][A-Za-z0-9_]*)\b(?:(?!isHidden\s*=\s*true).)*$",
                    content,
                    re.DOTALL
                )
                
                for match in hierarchy_matches:
                    hierarchy_name = match.group(1)
                    if is_pascalcase_without_spaces(hierarchy_name):
                        violations.append({
                            'type': 'hierarchy',
                            'name': hierarchy_name,
                            'line': content.count('\n', 0, match.start()) + 1,
                            'file': file_path
                        })
                    
            except Exception as e:
                st.warning(f"Error checking file {file_path}: {str(e)}")
                continue
            
        return violations if violations else None

    def fix_pascalcase_columns_hierarchies(self, violations):
        """Fix PascalCase violations in columns and hierarchies by adding spaces."""
        try:
            # Group violations by file
            violations_by_file = {}
            for violation in violations:
                file_path = Path(violation['file'])
                if file_path not in violations_by_file:
                    violations_by_file[file_path] = []
                violations_by_file[file_path].append(violation)
            
            # Fix violations in each file
            for file_path, file_violations in violations_by_file.items():
                with open(file_path, "r", encoding='utf-8') as f:
                    content = f.read()
                
                # Fix each violation
                for violation in file_violations:
                    old_name = violation['name']
                    # Add spaces before capital letters (except the first one)
                    new_name = re.sub(r'(?<!^)(?<![\W_])([A-Z][a-z])', r' \1', old_name)
                    
                    # Replace the name in the content
                    content = re.sub(
                        rf"{violation['type']}\s+{re.escape(old_name)}\b",
                        f"{violation['type']} {new_name}",
                        content
                    )
                
                # Write the fixed content back
                with open(file_path, "w", encoding='utf-8') as f:
                    f.write(content)
            
            # Reload content after all fixes
            self.load_content()
            return None
            
        except Exception as e:
            st.error(f"Error fixing PascalCase violations: {str(e)}")
            return str(e)

def get_available_rules():
    """Get list of available rules that can be checked."""
    return [
        {
            "ID": "UPPERCASE_FIRST_LETTER_MEASURES_TABLES",
            "Name": "Measure and table names must start with uppercase letter",
            "Category": "Naming Conventions",
            "Description": "Avoid using prefixes and camelCasing. Use \"Sales\" instead of \"dimSales\" or \"mSales\".",
            "Severity": 2,
            "checker_method": "check_uppercase_first_letter_measures_tables",
            "fixer_method": "fix_uppercase_first_letter"
        },
        {
            "ID": "NO_PASCALCASE_COLUMNS_HIERARCHIES",
            "Name": "[Naming Conventions] Avoid PascalCase (without whitespaces) on visible columns and hierarchies",
            "Category": "Naming Conventions",
            "Description": "Visible columns and hierarchies should not use PascalCase in their names",
            "Severity": 2,
            "checker_method": "check_no_pascalcase_columns_hierarchies",
            "fixer_method": "fix_pascalcase_columns_hierarchies"
        }
    ]

def main():
    st.set_page_config(page_title="Power BI BPA Rule Checker", layout="wide")
    st.title("Power BI BPA Rule Checker")

    # Step 1: Browse project
    st.subheader("1. Select Semantic Model")
    
    # Folder path input
    project_folder = st.text_input(
        "Semantic Model Folder Path:",
        help="Path to the Semantic Model folder containing the 'definition' folder with model.tmdl"
    )
    
    # Add folder browse hint
    st.info("Enter the full path to your Semantic Model folder. Example: C:/Users/YourName/Documents/SemanticModel")
    
    if not project_folder:
        st.warning("Please enter a Semantic Model folder path to begin.")
        return
    
    # Load and validate semantic model
    model_path, error = load_semantic_model(project_folder)
    if error:
        st.error(error)
        return
        
    # Initialize rule checker
    checker = RuleChecker(model_path)
    
    # Step 2: Check for rule violations
    st.subheader("2. Rule Violations")
    
    # Get available rules
    rules = get_available_rules()
    
    # Check each rule for violations
    violations_found = False
    for rule in rules:
        checker_method = getattr(checker, rule['checker_method'])
        violations = checker_method()
        
        if violations:
            violations_found = True
            with st.expander(f"🔴 {rule['Name']} ({len(violations)} violations)"):
                st.markdown(f"""
                **Rule ID:** {rule['ID']}  
                **Category:** {rule['Category']}  
                **Severity:** {rule['Severity']}  
                **Description:** {rule['Description']}
                """)
                
                st.markdown("### Violations:")
                for v in violations:
                    file_name = Path(v['file']).name
                    st.markdown(f"- {v['type'].title()}: `{v['name']}` (in `{file_name}` line {v['line']})")
                    
                if st.button(f"Fix {rule['Name']}", key=f"fix_{rule['ID']}"):
                    error = getattr(checker, rule['fixer_method'])(violations)
                    if error:
                        st.error(error)
                    else:
                        st.success(f"Successfully fixed {rule['Name']} violations!")
                        st.rerun()
    
    if not violations_found:
        st.success("🟢 No rule violations found in the semantic model!")

if __name__ == "__main__":
    main()
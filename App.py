import os
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

def extract_json_array(content, start_marker):
    """Extract a JSON array from TMDL content starting at a specific marker."""
    try:
        # Find the start of the section
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return None, f"Could not find section: {start_marker}"
            
        # Move to the start of the array
        array_start = content.find('[', start_idx)
        if array_start == -1:
            return None, "Could not find start of array"
            
        # Initialize counters for brackets
        bracket_count = 1
        pos = array_start + 1
        
        # Track string state
        in_string = False
        escape_next = False
        
        # Find the matching closing bracket
        while pos < len(content) and bracket_count > 0:
            char = content[pos]
            
            if escape_next:
                escape_next = False
            elif char == '\\':
                escape_next = True
            elif char == '"' and not escape_next:
                in_string = not in_string
            elif not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    
            pos += 1
            
        if bracket_count != 0:
            return None, "Malformed JSON array: unmatched brackets"
            
        # Extract and parse the JSON array
        json_str = content[array_start:pos]
        return json.loads(json_str), None
        
    except json.JSONDecodeError as e:
        return None, f"JSON parsing error: {str(e)}"
    except Exception as e:
        return None, f"Error extracting JSON array: {str(e)}"

def load_bpa_rules(tmdl_path):
    """Load BPA rules from the model.tmdl file."""
    try:
        with open(tmdl_path, "r", encoding='utf-8') as f:
            content = f.read()
            
        # Extract the BPA rules array
        rules, error = extract_json_array(content, 'annotation BestPracticeAnalyzer =')
        if error:
            return [], error
            
        return rules, None
            
    except Exception as e:
        return [], f"Error loading BPA rules: {str(e)}"

def save_bpa_rules(tmdl_path, selected_rules):
    """Save selected BPA rules back to the model.tmdl file."""
    try:
        with open(tmdl_path, "r", encoding='utf-8') as f:
            content = f.read()
            
        # Find the BestPracticeAnalyzer annotation section
        start = content.find('annotation BestPracticeAnalyzer =')
        if start == -1:
            return "Could not find BestPracticeAnalyzer annotation in model.tmdl"
            
        # Find the array boundaries
        rules_start = content.find('[', start)
        if rules_start == -1:
            return "Could not find start of BPA rules array"
            
        # Initialize counters for brackets
        bracket_count = 1
        pos = rules_start + 1
        
        # Track string state
        in_string = False
        escape_next = False
        
        # Find the matching closing bracket
        while pos < len(content) and bracket_count > 0:
            char = content[pos]
            
            if escape_next:
                escape_next = False
            elif char == '\\':
                escape_next = True
            elif char == '"' and not escape_next:
                in_string = not in_string
            elif not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    
            pos += 1
            
        if bracket_count != 0:
            return "Malformed BPA rules array in model.tmdl"
            
        # Replace the rules array
        new_rules = json.dumps(selected_rules, indent=2)
        new_content = content[:rules_start] + new_rules + content[pos:]
        
        with open(tmdl_path, "w", encoding='utf-8') as f:
            f.write(new_content)
            
        return None
        
    except Exception as e:
        return f"Error saving BPA rules: {str(e)}"

def main():
    st.set_page_config(page_title="Power BI BPA Rule Manager", layout="wide")
    st.title("Power BI BPA Rule Manager")
    
    # Step 1: Browse project
    st.subheader("1. Select Semantic Model")
    project_folder = st.text_input(
        "Enter the path to your Semantic Model folder:",
        help="This should be the root folder containing the 'definition' folder with model.tmdl"
    )
    
    if not project_folder:
        st.info("Please enter the path to your Semantic Model folder to begin.")
        return
        
    # Load and validate semantic model
    model_path, error = load_semantic_model(project_folder)
    if error:
        st.error(error)
        return
        
    # Step 2: Load and select BPA rules
    st.subheader("2. Select BPA Rules")
    rules, error = load_bpa_rules(model_path)
    if error:
        st.error(error)
        return
        
    if not rules:
        st.warning("No BPA rules found in the model.")
        return
        
    # Create two columns for better organization
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Available Rules")
        # Create checkboxes for each rule with tooltips
        selected_rules = []
        for rule in rules:
            if st.checkbox(
                f"{rule['Name']}",
                help=f"""
                ID: {rule['ID']}
                Category: {rule['Category']}
                Severity: {rule['Severity']}
                Description: {rule['Description']}
                """,
                key=rule['ID']
            ):
                selected_rules.append(rule)
    
    with col2:
        st.markdown("### Selected Rules Summary")
        if selected_rules:
            for rule in selected_rules:
                st.markdown(f"✓ **{rule['Name']}**")
        else:
            st.info("No rules selected")
    
    # Step 3: Apply and save
    st.subheader("3. Apply Rules")
    if st.button("Apply Selected Rules", disabled=not selected_rules):
        error = save_bpa_rules(model_path, selected_rules)
        if error:
            st.error(error)
        else:
            st.success("✅ BPA rules successfully applied and saved!")
            st.balloons()

if __name__ == "__main__":
    main()
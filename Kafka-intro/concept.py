import streamlit as st
import uuid
from datetime import datetime

# Initialize session state variables if they don't exist
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'entities' not in st.session_state:
    st.session_state.entities = []
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}
if 'show_save_dialog' not in st.session_state:
    st.session_state.show_save_dialog = False
if 'show_draft_confirm' not in st.session_state:
    st.session_state.show_draft_confirm = False

# Mock user info
st.session_state.user_id = "user123"
st.session_state.business_role = "data_analyst"

# Navigation functions
def navigate_to(page):
    st.session_state.page = page
    st.session_state.show_save_dialog = False
    st.session_state.show_draft_confirm = False
    if page == 'entities_list':
        st.session_state.form_data = {}

def show_save_dialog():
    st.session_state.show_save_dialog = True

def hide_save_dialog():
    st.session_state.show_save_dialog = False

def show_draft_confirmation():
    st.session_state.show_draft_confirm = True
    
def hide_draft_confirmation():
    st.session_state.show_draft_confirm = False

# Define the draft confirmation dialog using st.dialog decorator
@st.dialog("Confirm Save as Draft")
def draft_confirmation_dialog():
    st.write("Are you sure you want to save this as a draft?")
    st.info("Only you and team members with the same role can see and edit drafts.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("No", key="draft_confirm_no"):
            hide_draft_confirmation()
            return False
    
    with col2:
        if st.button("Yes", key="draft_confirm_yes"):
            save_entity(as_draft=True)
            hide_draft_confirmation()
            hide_save_dialog()
            return True
    
    return False

# Define the save dialog using st.dialog decorator
@st.dialog("How would you like to save this item?")
def save_dialog():
    # Check validation
    all_fields_valid = (
        st.session_state.form_data.get('name', '') != '' and 
        st.session_state.form_data.get('description', '') != '' and 
        st.session_state.form_data.get('system', '') != ''
    )
    
    # Dialog content based on validation
    if not all_fields_valid:
        st.warning("Some required fields are missing or invalid.")
        with st.expander("View validation issues"):
            if st.session_state.form_data.get('description', '') == '':
                st.warning("• Description field is empty")
            if st.session_state.form_data.get('system', '') == '':
                st.warning("• System field is empty")
        
        st.info("You can save this as a draft to complete later. Only you and team members with the same role can see and edit drafts.")
    else:
        st.success("All required fields are valid.")
    
    # Dialog buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Save as Draft", key="dialog_draft_btn"):
            show_draft_confirmation()
            return False
    
    with col2:
        # Only enable full save if all validations pass
        save_disabled = not all_fields_valid
        if st.button("Save", key="dialog_save_btn", disabled=save_disabled):
            save_entity(as_draft=False)
            hide_save_dialog()
            return True
    
    return False

def save_entity(as_draft=False):
    # Generate a new ID if this is a new entity
    if 'id' not in st.session_state.form_data:
        st.session_state.form_data['id'] = str(uuid.uuid4())
        st.session_state.form_data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.form_data['created_by'] = st.session_state.user_id
    
    # Update modification info
    st.session_state.form_data['last_modified_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.form_data['last_modified_by'] = st.session_state.user_id
    st.session_state.form_data['is_draft'] = as_draft
    st.session_state.form_data['state'] = 'SAVED'
    
    # Check if we're updating an existing entity
    for i, entity in enumerate(st.session_state.entities):
        if entity.get('id') == st.session_state.form_data.get('id'):
            st.session_state.entities[i] = st.session_state.form_data
            hide_save_dialog()
            navigate_to('entities_list')
            return
    
    # Otherwise, add as new entity
    st.session_state.entities.append(st.session_state.form_data.copy())
    hide_save_dialog()
    navigate_to('entities_list')

# Sidebar navigation
with st.sidebar:
    st.title("MDQ Application")
    st.button("Manage Entities", on_click=navigate_to, args=('entities_list',))
    
    # Just for demo purposes - button to reset data
    if st.button("Reset Demo Data"):
        st.session_state.entities = []
        st.session_state.form_data = {}
        st.session_state.page = 'home'
        st.rerun()

# Main content area
if st.session_state.page == 'home':
    st.title("Mission Data Quality (MDQ)")
    st.write("Welcome to the MDQ application. Use the sidebar to navigate.")
    st.info("This is a mock application demonstrating the draft functionality.")

elif st.session_state.page == 'entities_list':
    st.title("Manage Entities")
    
    # Filter options
    filter_option = st.selectbox(
        "Filter by:",
        ["All Items", "Drafts Only", "Saved Only"],
        index=0
    )
    
    # Create new button
    st.button("Create New Entity", on_click=navigate_to, args=('create_entity',))
    
    # Display entities based on filter
    filtered_entities = st.session_state.entities
    if filter_option == "Drafts Only":
        filtered_entities = [e for e in st.session_state.entities if e.get('is_draft', False)]
    elif filter_option == "Saved Only":
        filtered_entities = [e for e in st.session_state.entities if not e.get('is_draft', False)]
    
    if filtered_entities:
        for entity in filtered_entities:
            # Create a status display
            status = entity.get('state', '')
            if entity.get('is_draft', False):
                status += " [DRAFT]"
                
            with st.expander(f"{entity.get('name', 'Unnamed')} - {status}"):
                st.write(f"**Description:** {entity.get('description', 'No description')}")
                st.write(f"**System:** {entity.get('system', 'No system')}")
                st.write(f"**Last Modified:** {entity.get('last_modified_at', 'Never')}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("View", key=f"view_{entity.get('id')}"):
                        st.session_state.form_data = entity.copy()
                        navigate_to('view_entity')
                with col2:
                    if st.button("Edit", key=f"edit_{entity.get('id')}"):
                        st.session_state.form_data = entity.copy()
                        navigate_to('edit_entity')
    else:
        st.info("No entities found.")

elif st.session_state.page == 'create_entity':
    st.title("Create New Entity")
    
    # Initialize form data if empty
    if not st.session_state.form_data:
        st.session_state.form_data = {
            'name': '',
            'description': '',
            'system': ''
        }
    
    # Entity form
    name = st.text_input("Name", value=st.session_state.form_data.get('name', ''))
    description = st.text_area("Description", value=st.session_state.form_data.get('description', ''))
    system = st.text_input("System", value=st.session_state.form_data.get('system', ''))
    
    # Update form data
    st.session_state.form_data['name'] = name
    st.session_state.form_data['description'] = description
    st.session_state.form_data['system'] = system
    
    # Check if name is provided
    name_missing = name.strip() == ''
    
    # Show error if name is missing
    if name_missing:
        st.error("Name is required.")
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel"):
            if st.session_state.form_data != {'name': '', 'description': '', 'system': ''}:
                confirm = st.warning("Are you sure you want to cancel? All changes will be lost.")
                if st.button("Yes, cancel"):
                    navigate_to('entities_list')
            else:
                navigate_to('entities_list')
    
    with col2:
        # Show a single save button that will trigger the dialog
        save_button = st.button("Save", disabled=name_missing)
        if save_button and not name_missing:
            show_save_dialog()

elif st.session_state.page == 'edit_entity':
    st.title("Edit Entity")
    
    # Check if editing a draft
    is_draft = st.session_state.form_data.get('is_draft', False)
    
    if is_draft:
        st.warning("""
        ### DRAFT MODE
        This item is saved as a draft and is incomplete. 
        Only you and team members with the same role can see it.
        """)
    
    # Entity form
    name = st.text_input("Name", value=st.session_state.form_data.get('name', ''))
    description = st.text_area("Description", value=st.session_state.form_data.get('description', ''))
    system = st.text_input("System", value=st.session_state.form_data.get('system', ''))
    
    # Update form data
    st.session_state.form_data['name'] = name
    st.session_state.form_data['description'] = description
    st.session_state.form_data['system'] = system
    
    # Check if name is provided
    name_missing = name.strip() == ''
    
    # Show error if name is missing
    if name_missing:
        st.error("Name is required.")
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel"):
            navigate_to('entities_list')
    
    with col2:
        # Show a single save button that will trigger the dialog
        save_button = st.button("Save", disabled=name_missing)
        if save_button and not name_missing:
            show_save_dialog()

elif st.session_state.page == 'view_entity':
    entity = st.session_state.form_data
    st.title(f"View Entity: {entity.get('name', 'Unnamed')}")
    
    # Check if viewing a draft
    is_draft = entity.get('is_draft', False)
    
    if is_draft:
        st.warning("""
        ### DRAFT MODE
        This item is saved as a draft and is incomplete. 
        Only you and team members with the same role can see it.
        """)
    
    # Display entity details
    st.write(f"**Name:** {entity.get('name', 'No name')}")
    st.write(f"**Description:** {entity.get('description', 'No description')}")
    st.write(f"**System:** {entity.get('system', 'No system')}")
    st.write(f"**Created At:** {entity.get('created_at', 'Unknown')}")
    st.write(f"**Created By:** {entity.get('created_by', 'Unknown')}")
    st.write(f"**Last Modified:** {entity.get('last_modified_at', 'Never')}")
    
    # Status display
    status = entity.get('state', '')
    if entity.get('is_draft', False):
        status += " [DRAFT]"
    st.write(f"**Status:** {status}")
    
    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back to List"):
            navigate_to('entities_list')
    
    with col2:
        if st.button("Edit"):
            navigate_to('edit_entity')

# Display dialogs when needed
if st.session_state.show_save_dialog and st.session_state.form_data.get('name', '').strip() != '':
    save_dialog()

# Show draft confirmation dialog if needed
if st.session_state.show_draft_confirm:
    draft_confirmation_dialog()


# Run the app
# When running this code, you'll see a Streamlit application with the specified behavior
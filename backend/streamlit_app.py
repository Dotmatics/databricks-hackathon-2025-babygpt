import streamlit as st
import asyncio
from datetime import datetime
from typing import Dict, List
import sys
import os

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent_manager import AgentManager
from plan_manager import PlanManager

# Configure page
st.set_page_config(
    page_title="BabyGPT - Your Pregnancy Assistant",
    page_icon="🤱",
    layout="wide"
)

# Initialize session state
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_created" not in st.session_state:
    st.session_state.user_created = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pregnancy_plan" not in st.session_state:
    st.session_state.pregnancy_plan = ""
if "agent_manager" not in st.session_state:
    st.session_state.agent_manager = AgentManager()
if "plan_manager" not in st.session_state:
    st.session_state.plan_manager = PlanManager()
if "plan_last_modified" not in st.session_state:
    st.session_state.plan_last_modified = None



async def create_user(username: str) -> bool:
    """Initialize a new user conversation."""
    try:
        # Start conversation with agent manager
        initial_response_chunks = []
        async for chunk in st.session_state.agent_manager.start_conversation(username):
            initial_response_chunks.append(chunk)
        
        initial_response = "".join(initial_response_chunks)
        
        if initial_response:
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": initial_response,
                "timestamp": datetime.now().strftime("%H:%M")
            })
        return True
    except Exception as e:
        st.error(f"Failed to create user: {str(e)}")
        return False

def get_pregnancy_plan(username: str) -> tuple[str, float]:
    """Fetch the current pregnancy plan from file system."""
    try:
        # First try to get from file system (persistent storage)
        plan_content = st.session_state.plan_manager.read_plan(username)
        
        if plan_content:
            # Get file modification time for change detection
            plan_path = st.session_state.plan_manager.get_plan_path(username)
            import os
            mod_time = os.path.getmtime(plan_path) if os.path.exists(plan_path) else 0
            return plan_content, mod_time
        else:
            return "No plan available yet.", 0
    except Exception as e:
        return f"Error loading plan: {str(e)}", 0

async def send_message(username: str, message: str) -> str:
    """Send a message and get response."""
    try:
        response_chunks = []
        async for chunk in st.session_state.agent_manager.process_message(username, message):
            response_chunks.append(chunk)
        return "".join(response_chunks)
    except Exception as e:
        return f"Error: {str(e)}"

def run_async(coro):
    """Helper function to run async code in Streamlit."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

def check_plan_updates():
    """Check for plan updates and refresh if needed."""
    if st.session_state.user_created and st.session_state.username:
        plan_content, mod_time = get_pregnancy_plan(st.session_state.username)
        
        # If plan was updated since last check
        if mod_time != st.session_state.plan_last_modified and mod_time > 0:
            st.session_state.pregnancy_plan = plan_content
            st.session_state.plan_last_modified = mod_time
            return True
    return False

# Check for plan updates on each page load
plan_updated = check_plan_updates()

# Main app layout
st.title("🤱 BabyGPT - Your Pregnancy Assistant")

# Show plan update notification if plan was auto-updated
if plan_updated:
    st.success("📋 Your pregnancy plan has been updated!")

# Sidebar for user setup and pregnancy plan
with st.sidebar:
    st.header("👤 User Profile")
    
    if not st.session_state.user_created:
        with st.form("user_setup"):
            username_input = st.text_input("Enter your username:", value=st.session_state.username)
            submit_user = st.form_submit_button("Start Your Pregnancy Journey")
            
            if submit_user and username_input:
                st.session_state.username = username_input
                with st.spinner("Initializing your pregnancy assistant..."):
                    success = run_async(create_user(username_input))
                if success:
                    st.session_state.user_created = True
                    st.success(f"Welcome, {username_input}! 🎉")
                    st.rerun()
                else:
                    st.error("Failed to create user. Please try again.")
    else:
        st.success(f"Logged in as: **{st.session_state.username}**")
        if st.button("New Session"):
            # Reset session but keep agent manager
            agent_manager = st.session_state.agent_manager
            for key in list(st.session_state.keys()):
                if key != "agent_manager":
                    del st.session_state[key]
            st.session_state.agent_manager = agent_manager
            st.rerun()
    
    # Pregnancy Plan Section
    if st.session_state.user_created:
        st.header("📋 Your Pregnancy Plan")
        
        # Auto-refresh plan with change detection
        plan_content, mod_time = get_pregnancy_plan(st.session_state.username)
        
        # Check if plan has been updated
        if mod_time != st.session_state.plan_last_modified:
            st.session_state.pregnancy_plan = plan_content
            st.session_state.plan_last_modified = mod_time
            if mod_time > 0:  # Only show update notification if file exists
                st.toast("📋 Plan updated!", icon="✅")
        
        # Manual refresh button
        if st.button("🔄 Refresh Plan"):
            plan_content, mod_time = get_pregnancy_plan(st.session_state.username)
            st.session_state.pregnancy_plan = plan_content
            st.session_state.plan_last_modified = mod_time
            st.success("Plan refreshed!")
        
        # Display the plan
        if st.session_state.pregnancy_plan and st.session_state.pregnancy_plan != "No plan available yet.":
            # Plan statistics at the top
            plan_lines = len([line for line in st.session_state.pregnancy_plan.split('\n') if line.strip()])
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📊 Plan Lines", plan_lines)
            with col2:
                if mod_time > 0:
                    last_updated = datetime.fromtimestamp(mod_time).strftime('%m/%d %H:%M')
                    st.metric("🕒 Last Updated", last_updated)
            
            # Show plan in an expandable container for better readability
            with st.expander("📋 View Full Plan", expanded=True):
                st.markdown(st.session_state.pregnancy_plan)
            
            # Download button
            st.download_button(
                label="📥 Download Plan",
                data=st.session_state.pregnancy_plan,
                file_name=f"{st.session_state.username}_pregnancy_plan.md",
                mime="text/markdown",
                help="Download your pregnancy plan as a Markdown file"
            )
        else:
            st.info("Your personalized pregnancy plan will appear here as you chat with the assistant.")
            
            # Check if plan exists but failed to load
            if st.session_state.pregnancy_plan.startswith("Error"):
                st.error("Failed to load plan. Please check your username or try refreshing.")

# Main chat interface
if st.session_state.user_created:
    st.header("💬 Chat with Your Pregnancy Assistant")
    
    # Display chat history
    for i, message in enumerate(st.session_state.chat_history):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
            # Add timestamp
            if "timestamp" in message:
                st.caption(f"*{message['timestamp']}*")
            

    
    # Chat input
    if prompt := st.chat_input("Ask about pregnancy, healthcare providers, or your plan..."):
        # Add user message to history
        user_message = {
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().strftime("%H:%M")
        }
        st.session_state.chat_history.append(user_message)
        
        # Display user message immediately
        with st.chat_message("user"):
            st.write(prompt)
            st.caption(f"*{user_message['timestamp']}*")
        
        # Get assistant response
        with st.chat_message("assistant"):
            with st.spinner("Getting response..."):
                response = run_async(send_message(st.session_state.username, prompt))
            
            if response and not response.startswith("Error:"):
                st.write(response)
                timestamp = datetime.now().strftime("%H:%M")
                st.caption(f"*{timestamp}*")
                

                
                # Add assistant message to history
                assistant_message = {
                    "role": "assistant",
                    "content": response,
                    "timestamp": timestamp
                }
                st.session_state.chat_history.append(assistant_message)
                
                # Refresh pregnancy plan after interaction (plan will auto-update on next rerun)
                # Force a slight delay to ensure plan file is written
                import time
                time.sleep(0.1)
                
                st.rerun()
            else:
                st.error(f"Failed to get response: {response}")

else:
    # Welcome screen
    st.markdown("""
    ## Welcome to BabyGPT! 🤱
    
    Your AI-powered pregnancy support assistant is here to help you navigate your pregnancy journey from conception to birth.
    
    ### What I can help you with:
    - 🏥 **Healthcare Provider Selection**: Find providers based on your location and insurance
    - 📅 **Appointment Management**: Track upcoming appointments and know what to expect
    - 📚 **Pregnancy Information**: Trimester-specific advice and fetal development
    - 🥗 **Nutrition & Lifestyle**: Evidence-based recommendations for healthy pregnancy
    - 📋 **Birth Plan Creation**: Help you prepare for labor and delivery
    - 🤱 **Postpartum Support**: Breastfeeding and early care guidance
    
    ### Getting Started:
    1. Enter your username in the sidebar
    2. Click "Start Your Pregnancy Journey"
    3. Begin chatting with your personalized pregnancy assistant
    4. Your pregnancy plan will be created and updated as we chat
    
    **Please note**: While I provide evidence-based information, always consult with your healthcare provider for personalized medical advice.
    """)
    
    # Quick start tips
    with st.expander("💡 Tips for Getting Started"):
        st.markdown("""
        - **Be specific**: Tell me your current trimester, location, or specific concerns
        - **Ask about providers**: "Find OB/GYN providers near [your city]"
        - **Track appointments**: "I have my first prenatal appointment next week"
        - **Get advice**: "What should I eat during my second trimester?"
        - **Plan ahead**: "Help me create a birth plan"
        """)

# Footer
st.markdown("---")
st.markdown(
    "*BabyGPT is designed to provide informational support. "
    "Always consult with qualified healthcare professionals for medical decisions.*"
)

# Auto-refresh toggle in sidebar
if st.session_state.user_created:
    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh plan", value=True, 
                                      help="Automatically check for plan updates")
    
    if auto_refresh:
        # Add a small delay and rerun to create auto-refresh effect
        import time
        if st.sidebar.button("🔁 Check for updates now"):
            time.sleep(0.1)  # Small delay
            st.rerun()

# Development info
if st.sidebar.button("🔧 Debug Info"):
    with st.sidebar.expander("Debug Information"):
        st.write("**Session State:**")
        debug_state = {k: str(v)[:100] + "..." if len(str(v)) > 100 else v 
                      for k, v in st.session_state.items() 
                      if k not in ["agent_manager", "plan_manager"]}
        st.write(debug_state) 
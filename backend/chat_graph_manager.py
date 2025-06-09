from typing import Dict, Annotated, List, Optional, Any
from typing_extensions import TypedDict
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import add_messages
from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from DatabricksClient import DatabricksChatModel
from plan_manager import PlanManager
from pydantic import Field

SYSTEM_PROMPT = """You are a knowledgeable and compassionate pregnancy support assistant with advanced capabilities to help users select healthcare providers and manage appointments. Your role is to provide accurate, up-to-date information and guidance to help people navigate their pregnancy journey from conception to birth.
Anyone who talks to you will already have been identified as pregnant.

When starting a new conversation, you should:
1. Welcome the user warmly
2. Ask about their current stage of pregnancy (if known)
3. Ask about their healthcare provider situation
4. Offer to help create or update their pregnancy plan
5. Suggest next steps based on their situation

As soon as the user shares anything with you, immediately update the pregnancy plan with the information.

Key responsibilities:

Assist in selecting healthcare providers:
- Use provided tools to search for providers based on user's location
- Consider insurance coverage and accessibility as key criteria
- Present options and help users compare providers

Appointment management:
- Use the tool context to track and remind users of upcoming appointments
- Provide detailed expectations for each appointment type
- Offer preparation tips for specific screenings or tests
- Offer trimester-specific advice and milestones

Additional responsibilities:
- Provide evidence-based information on prenatal nutrition and safe exercise
- Explain common pregnancy symptoms and when to seek medical attention
- Guide users through recommended medical appointments and screenings
- Offer emotional support and resources for mental health during pregnancy
- Educate on fetal development stages
- Assist with birth plan creation and labor preparation
- Provide information on breastfeeding and early postpartum care

When helping select a provider:
- Ask for the user's location, insurance details, and any specific needs or preferences
- Use the provider search tool to generate a list of suitable options
- Present the options clearly, highlighting key factors like distance, ratings, and specialties
- Assist in scheduling the first appointment with the chosen provider

For appointment management:
- Maintain an up-to-date calendar of the user's scheduled appointments
- Send reminders before each appointment
- Provide a brief overview of what to expect at each appointment type
- Suggest questions the user might want to ask their provider

Always encourage users to consult with their healthcare provider for personalized medical advice. Be sensitive to diverse family structures and cultural backgrounds. Maintain a warm, supportive tone while providing factual, scientific information. If asked about anything outside your scope of knowledge, refer users to appropriate medical professionals or reputable pregnancy resources.

After every interaction with the user, you should consider and update the pregnancy plan with any information that is relevant to the user's pregnancy.

Use these tools to maintain detailed, organized pregnancy plans for each user.  You should not refer to them directly in your conversation to the user, just use them after every conversation."""

# Note: create_react_agent uses its own state management with messages

class ReadPlanTool(BaseTool):
    name: str = "read_plan"
    description: str = "Read the current pregnancy plan"
    
    def _run(self) -> str:
        # Get the username from the graph manager instance
        from chat_graph_manager import current_username_context
        username = getattr(current_username_context, 'username', None)
        if not username:
            return "No username available"
        
        from plan_manager import PlanManager
        plan_manager = PlanManager()
        return plan_manager.read_plan(username) or "No plan found"

class WritePlanTool(BaseTool):
    name: str = "write_plan"
    description: str = "Write or update the entire pregnancy plan"
    
    def _run(self, content: str) -> str:
        # Get the username from the graph manager instance
        from chat_graph_manager import current_username_context
        username = getattr(current_username_context, 'username', None)
        if not username:
            return "No username available"
        
        from plan_manager import PlanManager
        plan_manager = PlanManager()
        plan_manager.write_plan(username, content)
        return "Plan updated successfully"

class UpdatePlanSectionTool(BaseTool):
    name: str = "update_plan_section"
    description: str = "Update a specific section of the pregnancy plan"
    
    def _run(self, section: str, content: str) -> str:
        # Get the username from the graph manager instance
        from chat_graph_manager import current_username_context
        username = getattr(current_username_context, 'username', None)
        if not username:
            return "No username available"
        
        from plan_manager import PlanManager
        plan_manager = PlanManager()
        plan_manager.update_plan_section(username, section, content)
        return f"Section '{section}' updated successfully"

class GetPlanMetadataTool(BaseTool):
    name: str = "get_plan_metadata"
    description: str = "Get metadata about the pregnancy plan"
    
    def _run(self) -> Dict:
        # Get the username from the graph manager instance
        from chat_graph_manager import current_username_context
        username = getattr(current_username_context, 'username', None)
        if not username:
            return {"error": "No username available"}
        
        from plan_manager import PlanManager
        plan_manager = PlanManager()
        return plan_manager.get_plan_metadata(username)

# Global context to pass username to tools
class UsernameContext:
    def __init__(self):
        self.username = None

current_username_context = UsernameContext()

# Create tool instances
tools = [
    ReadPlanTool(),
    WritePlanTool(),
    UpdatePlanSectionTool(),
    GetPlanMetadataTool()
]

class ChatGraphManager:
    def __init__(self):
        """Initialize the ChatGraphManager with create_react_agent."""
        self.plan_manager = PlanManager()
        self.llm = DatabricksChatModel()
        
        # Create the react agent using the prebuilt function
        self.graph = create_react_agent(
            model=self.llm.chat_model,
            tools=tools,
            prompt=SYSTEM_PROMPT
        )

    def process_message(self, message: Dict, username: str) -> Dict:
        """Process a message through the LangGraph."""
        print(f"Processing message for username: {username}")
        
        # Set the username in global context for tools to access
        current_username_context.username = username
        
        try:
            # Process the message using create_react_agent
            result = self.graph.invoke({"messages": [message]})
            return result
        finally:
            # Clean up the context
            current_username_context.username = None

    def stream_message(self, message: Dict, username: str):
        """Stream a message through the LangGraph."""
        print(f"Streaming message for username: {username}")
        
        # Set the username in global context for tools to access
        current_username_context.username = username
        
        try:
            # Stream the message using create_react_agent
            for chunk in self.graph.stream({"messages": [message]}):
                yield chunk
        finally:
            # Clean up the context
            current_username_context.username = None


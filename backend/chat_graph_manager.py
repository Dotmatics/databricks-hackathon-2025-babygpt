from typing import Dict, Annotated, List, Optional, Any
from typing_extensions import TypedDict
from langgraph.prebuilt import create_react_agent
from langgraph.graph.message import add_messages
from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from DatabricksClient import DatabricksChatModel
from plan_manager import PlanManager
from pydantic import Field
from langchain_mcp_adapters.client import MultiServerMCPClient
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables from the backend folder
env_path = os.path.join(os.path.dirname(__file__), '.env')
dotenv_loaded = load_dotenv(env_path)


#
SYSTEM_PROMPT = """You are a knowledgeable and compassionate pregnancy support assistant with advanced capabilities to help users select healthcare providers and manage appointments. Your role is to provide accurate, up-to-date information and guidance to help people navigate their pregnancy journey from conception to birth.
Anyone who talks to you will already have been identified as pregnant.

When the conversation starts, read the pregnancy plan for the user and use it to start the conversation.

When starting a new conversation, you should:
1. Welcome the user warmly
2. Ask about their current stage of pregnancy (if known)
3. Ask about their healthcare provider situation
4. Suggest next steps based on their situation

Present your questions in an outlined format that is easy to read.  This should be like a checklist with some items checked or crossed out because they are completed.

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

Use these tools to maintain detailed, organized pregnancy plans for each user. You should not refer to them directly in your conversation to the user, just use them after every conversation."""

# Note: create_react_agent uses its own state management with messages

nimble_token = os.getenv("NIMBLE_TOKEN",'')

client = MultiServerMCPClient({
    "nimble": {
        "url": "https://mcp.nimbleway.com/sse",
        "transport": "sse",
        "headers": {
            "Authorization": f"Bearer {nimble_token}"
        }
    }
})

mcp_tools = asyncio.run(client.get_tools())
nimble_agent = create_react_agent(
    model=DatabricksChatModel().chat_model,
    tools=mcp_tools,
    prompt="Using the tools provided your aim is to provide the best options for OBGYN provider"
)

class GetOBGYNProviderOptions(BaseTool):
    name: str = "find_provider"
    description: str = "Finds OBGYN providers based on the user's location"

    def _run(self) -> str:
        from chat_graph_manager import current_location_context
        location = getattr(current_location_context, 'location', None)
        if not location:
            return "Please set your location first using the set_users_location tool"

        try:
            result = nimble_agent.invoke({"messages": [{"role": "user", "content": f"What OBGYN Providers are available near {location}"}]})
            # Extract the final message content from the result
        
            if isinstance(result, dict) and 'messages' in result:
                return result['messages'][-1].content if result['messages'] else "No providers found"
            return str(result)
        except Exception as e:
            return f"Error finding providers: {str(e)}"


class SetUsersLocation(BaseTool):
    name: str = "set_users_location"
    description: str = "Set the user's location"
    def _run(self, location: str) -> str:
        from chat_graph_manager import current_location_context
        current_location_context.location = location
        return "Location set successfully you can now use the find_provider tool to find OBGYN providers"

    

class ReadPlanTool(BaseTool):
    name: str = "read_plan"
    description: str = "Read the current pregnancy plan for the user"
    
    def _run(self) -> str:
        # Get the username from the graph manager instance
        from chat_graph_manager import current_username_context
        username = getattr(current_username_context, 'username', None)
        if not username:
            return "No username available"
        
        from plan_manager import PlanManager
        plan_manager = PlanManager()
        plan_content = plan_manager.read_plan(username)
        return plan_content if plan_content else "No existing pregnancy plan found for this user.\n"

class WritePlanTool(BaseTool):
    name: str = "write_plan"
    description: str = "Write or completely update the pregnancy plan for the user with new content"
    
    def _run(self, content: str) -> str:
        # Get the username from the graph manager instance
        from chat_graph_manager import current_username_context
        username = getattr(current_username_context, 'username', None)
        if not username:
            return "No username available"
        
        from plan_manager import PlanManager
        plan_manager = PlanManager()
        plan_manager.write_plan(username, content)
        return "Pregnancy plan updated successfully"

# Global context to pass username to tools
class UsernameContext:
    def __init__(self):
        self.username = None

class LocationContext:
    def __init__(self):
        self.location = None

current_location_context = LocationContext()
current_username_context = UsernameContext()

# Create tool instances
tools = [
    ReadPlanTool(),
    WritePlanTool(),
    GetOBGYNProviderOptions(),
    SetUsersLocation()
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

    def process_message(self, messages: List[Dict], username: str) -> Dict:
        """Process messages with full conversation history through the LangGraph."""
        print(f"Processing message for username: {username}\n")
        
        # Set the username in global context for tools to access
        current_username_context.username = username
        
        try:
            # Process the messages using create_react_agent with full history
            result = self.graph.invoke({"messages": messages})
            return result
        finally:
            # Clean up the context
            current_username_context.username = None

    def stream_message(self, messages: List[Dict], username: str):
        """Stream messages with full conversation history through the LangGraph."""
        print(f"Streaming message for username: {username}\n")
        
        # Set the username in global context for tools to access
        current_username_context.username = username
        
        try:
            # Stream the messages using create_react_agent with full history
            for chunk in self.graph.stream({"messages": messages}):
                yield chunk
        finally:
            # Clean up the context
            current_username_context.username = None


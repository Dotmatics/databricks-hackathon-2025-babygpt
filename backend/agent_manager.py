from typing import AsyncGenerator, Dict, List, Optional
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput
import json
import asyncio
from datetime import datetime
from chat_graph_manager import ChatGraphManager
from plan_manager import PlanManager

class AgentManager:
    def __init__(self, workspace_client: Optional[WorkspaceClient] = None):
        """Initialize the AgentManager with optional workspace client for Databricks integration."""
        self.workspace_client = workspace_client
        self.conversation_history: Dict[str, List[Dict]] = {}  # username -> messages
        self.pregnancy_plans: Dict[str, Dict] = {}  # username -> plan data
        self.chat_graph = ChatGraphManager()
        self.plan_manager = PlanManager()

    async def start_conversation(self, username: str) -> AsyncGenerator[str, None]:
        """Initialize a new conversation for a user and get initial response."""
        if username not in self.conversation_history:
            self.conversation_history[username] = []
            self.pregnancy_plans[username] = {
                "content": "",
                "last_updated": datetime.now().isoformat()
            }
            # Note: Plan will be automatically initialized when first written to by the agent
            
            # Create initial message to start the conversation
            initial_message = {
                "role": "user",
                "content": "Hello, I'm ready to help you with your pregnancy journey. Let's get started!",
                "timestamp": datetime.now().isoformat()
            }
            
            # Add to conversation history
            self.conversation_history[username].append(initial_message)
            
            # Process the conversation (which now has the initial message)
            async for chunk in self.process_message(username, initial_message["content"]):
                yield chunk

    async def process_message(self, username: str, message: str) -> AsyncGenerator[str, None]:
        """Process a user message and yield responses as they come in."""
        if username not in self.conversation_history:
            await self.start_conversation(username)

        # Add user message to history
        user_message = {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        }
        self.conversation_history[username].append(user_message)

        try:
            # Convert conversation history to the format expected by LangGraph
            langgraph_messages = []
            for msg in self.conversation_history[username]:
                langgraph_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Process message through ChatGraphManager with full history
            response_content = ""
            for event in self.chat_graph.stream_message(langgraph_messages, username):
                for value in event.values():
                    if "messages" in value and value["messages"]:
                        response = value["messages"][-1]
                        response_content = response.content
                        yield response.content

            # Add assistant response to history
            self.conversation_history[username].append({
                "role": "assistant",
                "content": response_content,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            error_message = f"Error processing message: {str(e)}"
            yield error_message
            self.conversation_history[username].append({
                "role": "system",
                "content": error_message,
                "timestamp": datetime.now().isoformat()
            })

    async def get_conversation_history(self, username: str) -> List[Dict]:
        """Get the conversation history for a user."""
        return self.conversation_history.get(username, [])

    async def get_pregnancy_plan(self, username: str) -> Dict:
        """Get the pregnancy plan for a user."""
        return self.pregnancy_plans.get(username, {
            "content": "",
            "last_updated": datetime.now().isoformat()
        })

    async def update_pregnancy_plan(self, username: str, content: str) -> Dict:
        """Update the pregnancy plan for a user."""
        if username not in self.pregnancy_plans:
            await self.start_conversation(username)
        
        self.pregnancy_plans[username] = {
            "content": content,
            "last_updated": datetime.now().isoformat()
        }
        return self.pregnancy_plans[username]
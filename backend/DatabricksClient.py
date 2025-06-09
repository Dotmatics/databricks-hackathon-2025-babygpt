from databricks_langchain import ChatDatabricks
import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

# Load environment variables from .env file
load_dotenv()

class DatabricksChatModel:
    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        endpoint: str = "databricks-claude-sonnet-4",
        temperature: float = 0.1,
        max_tokens: int = 250
    ):
        # Use environment variables if not provided
        self.host = host or os.getenv("DATABRICKS_HOST")
        self.token = token or os.getenv("DATABRICKS_TOKEN")
        
        if not self.host or not self.token:
            raise ValueError("Databricks host and token must be provided either through parameters or environment variables")
            
        # Set environment variables
        os.environ["DATABRICKS_HOST"] = self.host
        os.environ["DATABRICKS_TOKEN"] = self.token
            
        self.chat_model = ChatDatabricks(
            endpoint=endpoint,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.tools = None
    
    def bind_tools(self, tools: List[Any]) -> 'DatabricksChatModel':
        """Bind tools to the chat model."""
        self.tools = tools
        self.chat_model = self.chat_model.bind_tools(tools)
        return self
    
    def invoke(self, messages: List[Dict[str, Any]]) -> BaseMessage:
        """Invoke the chat model with messages."""
        return self.chat_model.invoke(messages)


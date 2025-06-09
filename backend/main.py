from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import json
import argparse
import asyncio
from agent_manager import AgentManager

app = FastAPI(title="BabyGPT API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the agent manager
agent_manager = AgentManager()

class User(BaseModel):
    username: str

class ChatMessage(BaseModel):
    content: str
    role: str = "user"

class PregnancyPlan(BaseModel):
    content: str
    last_updated: str

@app.post("/users")
async def create_user(user: User):
    """Create a new user and get initial response from the agent."""
    response_chunks = []
    async for chunk in agent_manager.start_conversation(user.username):
        response_chunks.append(chunk)
    return {
        "username": user.username, 
        "status": "created",
        "initial_response": "".join(response_chunks)
    }

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            username = message_data.get("username")
            message = message_data.get("message")
            
            if not username or not message:
                await websocket.send_text(json.dumps({
                    "error": "Missing username or message"
                }))
                continue

            async for chunk in agent_manager.process_message(username, message):
                await websocket.send_text(json.dumps({
                    "chunk": chunk
                }))
    except Exception as e:
        await websocket.close()

@app.get("/plan/{username}")
async def get_pregnancy_plan(username: str):
    plan = await agent_manager.get_pregnancy_plan(username)
    return plan

@app.post("/plan/{username}")
async def update_pregnancy_plan(username: str, plan: PregnancyPlan):
    updated_plan = await agent_manager.update_pregnancy_plan(username, plan.content)
    return updated_plan

async def cli_chat():
    """Command line interface for testing the chat functionality."""
    print("Welcome to BabyGPT CLI mode!")
    username = input("Please enter your username: ")
    
    print("\nInitializing conversation...")
    async for chunk in agent_manager.start_conversation(username):
        print(chunk, end="", flush=True)
    print("\n")
    
    print("\nType 'exit' to quit")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() == 'exit':
            break
            
        print("\nAssistant: ", end="", flush=True)
        async for chunk in agent_manager.process_message(username, user_input):
            print(chunk, end="", flush=True)
        print()  # New line after response

def main():
    parser = argparse.ArgumentParser(description='BabyGPT Backend')
    parser.add_argument('--cli', action='store_true', help='Run in CLI mode')
    args = parser.parse_args()

    if args.cli:
        asyncio.run(cli_chat())
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()

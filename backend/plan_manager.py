import os
from datetime import datetime
from typing import Optional

class PlanManager:
    def __init__(self, plans_dir: str = "plans"):
        """Initialize the PlanManager with a directory for storing plans."""
        self.plans_dir = plans_dir
        self._ensure_base_directory()

    def _ensure_base_directory(self):
        """Ensure the base plans directory exists."""
        os.makedirs(self.plans_dir, exist_ok=True)

    def _ensure_user_directory(self, username: str):
        """Ensure the user-specific directory exists."""
        user_dir = os.path.join(self.plans_dir, username)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def get_plan_path(self, username: str) -> str:
        """Get the path to a user's plan file."""
        user_dir = self._ensure_user_directory(username)
        return os.path.join(user_dir, "pregnancy_plan.md")
    
    def read_plan(self, username: str) -> Optional[str]:
        """Read a user's pregnancy plan. Returns None if no plan exists."""
        plan_path = self.get_plan_path(username)
        if os.path.exists(plan_path):
            with open(plan_path, 'r') as f:
                x = f.read()
                print(f"Plan for {username}: {x}\n")
                return x
        return None

    def write_plan(self, username: str, content: str) -> None:
        """Write or completely replace a user's pregnancy plan."""
        plan_path = self.get_plan_path(username)
        print(f"Writing plan for {username}\n")
        
        # If no plan exists, create one with basic structure
        if not os.path.exists(plan_path):
            header = f"""# Pregnancy Plan for {username}

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*

"""
            content = header + content
        
        with open(plan_path, 'w') as f:
            f.write(content) 
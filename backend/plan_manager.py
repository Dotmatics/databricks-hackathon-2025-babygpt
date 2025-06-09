import os
from datetime import datetime
from typing import Dict, Optional

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
        """Read a user's pregnancy plan."""
        plan_path = self.get_plan_path(username)
        if os.path.exists(plan_path):
            with open(plan_path, 'r') as f:
                return f.read()
        return None

    def write_plan(self, username: str, content: str) -> None:
        """Write or update a user's pregnancy plan."""
        plan_path = self.get_plan_path(username)
        print(f"Writing plan for {username}")
        with open(plan_path, 'w') as f:
            f.write(content)

    def update_plan_section(self, username: str, section: str, content: str) -> None:
        """Update a specific section of a user's pregnancy plan."""
        print(f"Updating plan section for {username}")
        current_plan = self.read_plan(username) or ""
        
        # If the section already exists, update it
        section_header = f"## {section}\n"
        if section_header in current_plan:
            # Split the content into sections
            sections = current_plan.split("## ")
            new_sections = []
            for s in sections:
                if s.startswith(section):
                    new_sections.append(f"{section}\n{content}\n")
                else:
                    new_sections.append(s)
            new_plan = "## ".join(new_sections)
        else:
            # Add new section
            new_plan = f"{current_plan}\n\n{section_header}{content}\n"
        
        self.write_plan(username, new_plan)

    def get_plan_metadata(self, username: str) -> Dict:
        """Get metadata about a user's plan."""
        plan_path = self.get_plan_path(username)
        if os.path.exists(plan_path):
            return {
                "last_updated": datetime.fromtimestamp(os.path.getmtime(plan_path)).isoformat(),
                "file_size": os.path.getsize(plan_path),
                "plan_path": plan_path
            }
        return {
            "last_updated": None,
            "file_size": 0,
            "plan_path": plan_path
        }

    def initialize_user_plan(self, username: str) -> None:
        """Initialize a new user's plan with a basic structure."""
        if not self.read_plan(username):
            print(f"Initializing plan for {username}")
            initial_content = f"""# Pregnancy Plan for {username}

## Personal Information
- Created: {datetime.now().strftime('%Y-%m-%d')}

## Medical Information
- Due Date: TBD
- Healthcare Provider: TBD

## Appointments
- No appointments scheduled yet

## Notes
- Add your pregnancy-related notes here

## Questions for Healthcare Provider
- Add your questions here

## Resources
- Add helpful resources and links here
"""
            self.write_plan(username, initial_content) 
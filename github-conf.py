# scripts/create_project_action.py

import os
import sys
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("❌ SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ======================================================
# HELPERS
# ======================================================

def slugify(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def fetch_projects_in_db_order():
    """
    Fetch projects in stable DB order.
    Index = position in this list (1-based)
    """
    rows = (
        supabase
        .table("projects")
        .select("id,name,created_at")
        .eq("active", True)
        .order("created_at", desc=False)
        .execute()
        .data
        or []
    )
    return rows


# ======================================================
# MAIN
# ======================================================

def main():
    projects = fetch_projects_in_db_order()

    if not projects:
        print("❌ No active projects found")
        return

    print("\n📁 Active Projects (DB Order):\n")

    for idx, p in enumerate(projects, start=1):
        created = p["created_at"][:10]
        print(f"{idx}. {p['name']}  (created: {created})")

    try:
        project_index = int(input("\nSelect project index: "))
    except ValueError:
        print("❌ Invalid number")
        return

    if project_index < 1 or project_index > len(projects):
        print("❌ Index out of range")
        return

    project = projects[project_index - 1]
    project_name = project["name"]
    project_slug = slugify(project_name)

    print(f"\n✅ Selected project: {project_name}")
    print(f"📌 CLI index: {project_index}")

    interval_hours = int(
        input("⏱️  Run automation every how many hours? (e.g. 6): ")
    )

    # ======================================================
    # WORKFLOW TEMPLATE
    # ======================================================

    workflow = f"""
name: {project_name} – Automation

on:
  schedule:
    - cron: "0 */{interval_hours} * * *"
  workflow_dispatch:

jobs:
  automation:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run monitor
        env:
          SUPABASE_URL: ${{{{ secrets.SUPABASE_URL }}}}
          SUPABASE_SERVICE_ROLE_KEY: ${{{{ secrets.SUPABASE_SERVICE_ROLE_KEY }}}}
        run: |
          python cli.py monitor --project {project_index}

      - name: Run analyze
        env:
          SUPABASE_URL: ${{{{ secrets.SUPABASE_URL }}}}
          SUPABASE_SERVICE_ROLE_KEY: ${{{{ secrets.SUPABASE_SERVICE_ROLE_KEY }}}}
        run: |
          python cli.py analyze --project {project_index}

      - name: Run deliver
        env:
          TELEGRAM_BOT_TOKEN: ${{{{ secrets.TELEGRAM_BOT_TOKEN }}}}
          SUPABASE_URL: ${{{{ secrets.SUPABASE_URL }}}}
          SUPABASE_SERVICE_ROLE_KEY: ${{{{ secrets.SUPABASE_SERVICE_ROLE_KEY }}}}
        run: |
          python cli.py deliver --project {project_index}
"""

    path = f".github/workflows/project_{project_slug}.yml"
    os.makedirs(".github/workflows", exist_ok=True)

    with open(path, "w") as f:
        f.write(workflow.strip())

    print("\n🎉 GitHub Action created successfully!")
    print(f"👉 {path}")
    print("\n📌 Next steps:")
    print("1. git add .github/workflows/")
    print(f"2. git commit -m \"Add automation for project {project_name}\"")
    print("3. git push")


if __name__ == "__main__":
    main()

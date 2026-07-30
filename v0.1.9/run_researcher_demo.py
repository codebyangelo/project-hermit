import sqlite3
import os
from researcher import EvolutionResearcher
from orchestrator import Orchestrator

def main():
    db_path = "hermit_memory.db"
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    print("=== PROJECT HERMIT: INDEPENDENT RESEARCHER AGENT DEMO ===")
    
    # 1. Initialize orchestrator and researcher
    orchestrator = Orchestrator(db_path=db_path)
    researcher = EvolutionResearcher(db_path=db_path, orchestrator=orchestrator)
    
    # 2. Check current complex skills in database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT skill_name FROM active_skills WHERE description LIKE '%COMPLEX_NEEDS_FURTHER_RESEARCH%'")
    complex_skills = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    print(f"Complex Skills in Database: {complex_skills}")
    
    target_skill = "hex_search"
    if target_skill not in complex_skills:
        print(f"Adding '{target_skill}' to complex list for demonstration...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE active_skills SET description = '[Complex - Needs Further Research] ' || description WHERE skill_name = ?", (target_skill,))
        conn.commit()
        conn.close()
        
    # Get baseline code and description
    desc, code, version = orchestrator.get_skill(target_skill)
    # Strip any research notes tags
    clean_desc = desc
    if "=== RESEARCH_STATUS ===" in desc:
        clean_desc = desc.split("=== RESEARCH_STATUS ===")[0].strip()

    print(f"\nRunning failure analysis and research on skill: '{target_skill}'...")
    notes = researcher.research_failures(target_skill, code, clean_desc)
    
    if notes:
        print("\n=== GENERATED RESEARCH STRATEGY NOTE ===")
        print(notes)
        print("=========================================\n")
        print("Success! Research note has been written to the 'skill_research_notes' table in the database.")
    else:
        print("Error: Could not generate research strategy notes.")

if __name__ == "__main__":
    main()

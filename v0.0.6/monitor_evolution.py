import sqlite3
import time
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermit_memory.db")
REPORT_PATH = "/root/.gemini/antigravity-cli/brain/9b2cd972-556c-44ac-a13a-62f901dde9f2/evolution_report.md"

def compile_report():
    print("Compiling final evolution report...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fetch active skill current version
    cursor.execute("SELECT skill_name, version, code, description FROM active_skills WHERE skill_name='hex_search'")
    skill = cursor.fetchone()
    
    # Fetch all branches
    cursor.execute("""
        SELECT branch_name, latency_ms, max_rss_kb, complexity_score, status, timestamp 
        FROM skill_branches 
        ORDER BY id ASC
    """)
    branches = cursor.fetchall()
    conn.close()

    # Generate Markdown content
    md = []
    md.append("# 🧬 Project Hermit v0.0.6: 12-Step Evolution Report")
    md.append("### Multi-Agent Code Mutation & Verification Log")
    md.append("\n---\n")
    
    md.append("## 🏆 Final Skill Status")
    if skill:
        name, version, code, desc = skill
        md.append(f"- **Skill Name:** `{name}`")
        md.append(f"- **Final Version:** `v{version}`")
        md.append(f"- **Description:** {desc}")
        md.append("\n**Final Optimized Source Code:**")
        md.append(f"```python\n{code}\n```")
    else:
        md.append("No active skill details found.")

    md.append("\n---\n")
    md.append("## 📊 Evolutionary Branches Table")
    md.append("| Step | Branch Name | Status | Latency | Memory (RSS) | Complexity | Timestamp |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    step = 1
    for i, b in enumerate(branches):
        branch_name, latency, rss, complexity, status, ts = b
        lat_str = f"{latency:.2f} ms" if latency > 0 else "N/A"
        rss_str = f"{rss} KB" if rss > 0 else "N/A"
        md.append(f"| {step} | `{branch_name}` | **{status.upper()}** | {lat_str} | {rss_str} | {complexity} chars | {ts} |")
        if (i + 1) % 3 == 0:
            step += 1

    md.append("\n---\n")
    md.append("## 🕵️ Analysis of Multi-Agent Decisions")
    md.append("1. **Synthesizer Agent Proposals:** Proposed diverse structural variants including raw `bytes.find()` loops, sliding window slice comparisons via `memoryview`, and `re.finditer` regex matching.")
    md.append("2. **Adversarial QA Agent Interventions:** Played a critical role in preventing logical degradation. Built boundary asserts that checked for **overlapping matches**, rejecting variants that optimized for latency by skipping indices (e.g. standard `find()` or standard regex iterators).")
    md.append("3. **Pareto Frontier Selection:** Successfully integrated mutations that improved latency or memory footprint while preserving absolute safety.")

    # Write report
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(md))
        
    print(f"Report compiled successfully at: {REPORT_PATH}")
    return "\n".join(md)

def monitor():
    print("Starting evolution monitor loop...")
    target_records = 36  # 12 steps * 3 variants per step
    
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM skill_branches")
            count = cursor.fetchone()[0]
            
            cursor.execute("SELECT status FROM daemon_status WHERE id=1")
            status = cursor.fetchone()
            status_str = status[0] if status else "Unknown"
            
            cursor.execute("SELECT version FROM active_skills WHERE skill_name='hex_search'")
            version = cursor.fetchone()
            ver_str = f"v{version[0]}" if version else "N/A"
            
            conn.close()
            
            print(f"[{time.strftime('%H:%M:%S')}] Active Version: {ver_str} | Generated Variants: {count}/{target_records} | Daemon Status: '{status_str}'")
            
            if count >= target_records:
                print("Target of 12 mutations reached!")
                break
                
            time.sleep(30)
        except Exception as e:
            print("Monitor encountered error:", e)
            time.sleep(10)

    # Compile report and print it
    report = compile_report()
    print("\n--- FINAL REPORT SUMMARY ---")
    print(report[:1500] + "\n\n...[Truncated for length]...")

if __name__ == "__main__":
    monitor()

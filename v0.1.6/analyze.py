import os
import re

THOUGHTS_PATH = "/root/home/projects/project-hermit/v0.1.6/thoughts.txt"

def analyze_thoughts():
    if not os.path.exists(THOUGHTS_PATH):
        print(f"Error: Thoughts ledger not found at {THOUGHTS_PATH}")
        return

    # Let's read some parts of thoughts.txt and extract prompt and response sections
    print("Reading thoughts ledger...")
    with open(THOUGHTS_PATH, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Search for System Instruction: ..., Prompt: ...
    # and Success! ... Response: ...
    prompts = re.findall(r"Prompt:\n(.*?)(?=\nTX_OUTBOUND|\nRX_INBOUND|\n===|\Z)", content, re.DOTALL)
    responses = re.findall(r"Response:\n(.*?)(?=\nTX_OUTBOUND|\nRX_INBOUND|\n===|\Z)", content, re.DOTALL)

    print(f"Found {len(prompts)} prompts and {len(responses)} responses in thoughts ledger.")

    if prompts:
        avg_prompt_len = sum(len(p) for p in prompts) / len(prompts)
        print(f"Average Prompt Length: {avg_prompt_len:.1f} chars (~{avg_prompt_len/4:.1f} tokens)")
    if responses:
        avg_response_len = sum(len(r) for r in responses) / len(responses)
        print(f"Average Response Length: {avg_response_len:.1f} chars (~{avg_response_len/4:.1f} tokens)")

    # Print first prompt and response sample sizes
    if prompts and responses:
        print("\n--- SAMPLE PROMPT SIZE ---")
        print(f"Prompt length: {len(prompts[0])} chars")
        print("\n--- SAMPLE RESPONSE SIZE ---")
        print(f"Response length: {len(responses[0])} chars")

if __name__ == "__main__":
    analyze_thoughts();

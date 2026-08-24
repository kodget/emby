import json

log_path = r"C:\Users\USER\.gemini\antigravity-ide\brain\265a9b97-fb41-427d-a361-e3a6a14422af\.system_generated\logs\transcript_full.jsonl"
search_str = "generate_questions_task"

found_count = 0
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        if search_str in line:
            found_count += 1
            print(f"Found match {found_count}!")
            try:
                data = json.loads(line)
                # Look for tool calls or code contents in the step
                print("Step Index:", data.get("step_index"))
                print("Source:", data.get("source"))
                # Print keys or snippets
                content = data.get("content", "")
                if len(content) > 200:
                    print("Content snippet:", content[:200] + "...")
                else:
                    print("Content:", content)
            except Exception as e:
                print("Error parsing line:", e)
            print("-" * 50)

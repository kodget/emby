import json

log_path = r"C:\Users\USER\.gemini\antigravity-ide\brain\265a9b97-fb41-427d-a361-e3a6a14422af\.system_generated\logs\transcript_full.jsonl"

found_count = 0
with open(log_path, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if "tasks.py" in line:
            try:
                data = json.loads(line)
                calls = data.get("tool_calls", [])
                for call in calls:
                    args = call.get("args", {})
                    target = args.get("TargetFile", "")
                    if "tasks.py" in target:
                        found_count += 1
                        content = args.get("CodeContent") or args.get("ReplacementContent")
                        if content:
                            out_name = f"recovered_tasks_all_{found_count}.py"
                            with open(out_name, "w", encoding="utf-8") as out:
                                out.write(content)
                            print(f"Match {found_count}: Saved to {out_name} (length: {len(content)}, target: {target})")
            except Exception as e:
                pass

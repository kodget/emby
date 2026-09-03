import sys
with open(r'C:\Users\USER\.gemini\antigravity-ide\brain\9413547f-a1cc-423d-95db-f8d13c68552a\.system_generated\tasks\task-1080.log', 'r', encoding='utf-8') as f:
    html = f.read()

exc_start = html.find('<div class="exception_value">')
if exc_start != -1:
    exc_end = html.find('</div>', exc_start)
    print('Exception Value:', html[exc_start:exc_end])

trace_start = html.find('<textarea id="traceback_area"')
if trace_start != -1:
    trace_end = html.find('</textarea>', trace_start)
    print('Traceback:\n', html[trace_start:trace_end])

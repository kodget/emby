import re

with open('curriculum/urls.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for _ in range(10): # try 10 times to fix NameErrors
    try:
        compiled = compile(''.join(lines), 'curriculum/urls.py', 'exec')
        break
    except NameError as e:
        match = re.search(r"name '([^']+)' is not defined", str(e))
        if match:
            bad_name = match.group(1)
            for i, line in enumerate(lines):
                if bad_name in line and 'path(' in line:
                    lines[i] = '# ' + line
            
with open('curriculum/urls.py', 'w', encoding='utf-8') as f:
    f.write(''.join(lines))
print('Cleaned urls.py')

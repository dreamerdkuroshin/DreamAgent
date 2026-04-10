import sys
path = 'backend/tools/news.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip().startswith('async def llm_extract_facts_perspectives'):
        new_lines.append(line)
        new_lines.append('    cluster_articles = cluster_articles[:6]\n')
    elif 'get_source_badge(s[' in line:
        line = line.replace("{get_source_badge(s['url'])}", "🔗")
        new_lines.append(line)
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Success')

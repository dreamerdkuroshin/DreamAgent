import re
print(bool(re.search(r'(?<!\w)' + re.escape('c++') + r'(?!\w)', 'c++')))
print(bool(re.search(r'(?<!\w)' + re.escape('c++') + r'(?!\w)', 'I like c++')))
print(bool(re.search(r'(?<!\w)' + re.escape('book') + r'(?!\w)', 'booking')))
print(bool(re.search(r'(?<!\w)' + re.escape('ok') + r'(?!\w)', 'book')))
print(bool(re.search(r'(?<!\w)' + re.escape('ok') + r'(?!\w)', 'ok')))
print(bool(re.search(r'(?<!\w)' + re.escape('ok') + r'(?!\w)', 'it is ok')))

import sys
sys.path.insert(0, '.')
from server import smart_preprocess

with open('test_input.txt', 'r', encoding='utf-8') as f:
    raw = f.read()

result = smart_preprocess(raw)
with open('test_output.md', 'w', encoding='utf-8') as f:
    f.write(result)
print("Done, written to test_output.md")

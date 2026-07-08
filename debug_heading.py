import sys
sys.path.insert(0, '.')
from server import extract_heading

# 测试 "六、善法欲与贪欲的区别修行路上..."
text = "六、善法欲与贪欲的区别修行路上，还有一个容易混淆的问题"
start = text.find("六、")
heading, end = extract_heading(text, start, len("六、"))
print(f"heading='{heading}', end={end}")
print(f"remaining='{text[end:]}'")

# 测试 "二、中道：既不迷失，也不紧盯"
text2 = "二、中道：既不迷失，也不紧盯修行人最容易"
start2 = text2.find("二、")
heading2, end2 = extract_heading(text2, start2, len("二、"))
print(f"heading2='{heading2}', end={end2}")
print(f"remaining2='{text2[end2:]}'")

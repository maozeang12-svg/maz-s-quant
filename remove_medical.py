import re

path = r"C:\Users\11\Documents\Kimi\Workspaces\个人提升计划\create_resume.py"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 删除个人优势中的"医药"
content = content.replace(
    '深耕半导体、算力、医药产业链投研',
    '深耕半导体、算力产业链投研'
)

# 2. 删除沐龙工作经历中的医药投研整条
content = content.replace(
    '    ("", "医药投研：将半导体「卡脖子材料+国产替代」逻辑迁移至医药上游（纳微科技、惠泰医疗、恒瑞医药）"),\n',
    ''
)

# 3. 删除ETF中的"港股创新药"
content = content.replace(
    '港股创新药/香港证券/恒生科技',
    '港股ETF/香港证券/恒生科技'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("已删除医药相关内容")

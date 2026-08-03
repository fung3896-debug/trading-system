# 常用指令速查

## 场景1:日常记录对话
claude_trading "标题" \
  --summary "做了什么、发现了什么" \
  --todos "接下来要做的事" \
  --improvements "可以优化的方向"

## 场景2:开新对话前,先回顾进度
claude_todos
claude_improvements
claude_stats

## 场景3:确认代码现在长什么样
cd ~/Documents/PlanB_Scanner
git log --oneline -5
git status

## 场景4:改完代码后,提交存档
cd ~/Documents/PlanB_Scanner
git add 改过的文件名.py
git commit -m "简短说明这次改了什么"
git push

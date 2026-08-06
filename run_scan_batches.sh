#!/bin/bash
# 分批跑 industry_tier_scan.py，避免一次扫221支被Yahoo限流
LOG_DIR=~/Documents/PlanB_Scanner/scan_logs
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M)

echo "开始分批扫描 $(date)"

for i in 1 2 3 4 5 6 7 8 9; do
    echo "=== 第 $i 批 ==="
    python3 industry_tier_scan.py --batch $i --batch-size 25 >> "$LOG_DIR/scan_${TIMESTAMP}.log" 2>&1
    if [ $? -ne 0 ]; then
        echo "第 $i 批失败，5秒后重试一次"
        sleep 5
        python3 industry_tier_scan.py --batch $i --batch-size 25 >> "$LOG_DIR/scan_${TIMESTAMP}.log" 2>&1
    fi
    echo "第 $i 批完成，休息8秒"
    sleep 8
done

echo "全部批次跑完 $(date)"
echo "日志: $LOG_DIR/scan_${TIMESTAMP}.log"


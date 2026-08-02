# -*- coding: utf-8 -*-
"""
共享watchlist - MCDX和DWM都使用这个清单
"""

WATCHLIST = {
    'NASDAQ': [
        'NVDA', 'JBL', 'BX', 'AMD', 'META',
        'MSFT', 'INTC', 'AMZN', 'ARM', 'NVCT'
    ],
    'KLSE': [  # 22只，包含DWM DMA信号

        '7233.KL', '5211.KL', '8907.KL', '6459.KL', '5249.KL',  # 5只
        '5026.KL', '5286.KL', '0225.KL', '0099.KL', '5031.KL',  # 10只
        '5681.KL', '7163.KL', '8869.KL', '1066.KL', '0215.KL',  # 15只
        '0326.KL', '7103.KL', '5263.KL', '4863.KL', '5243.KL',  # 20只
        '5142.KL', '2453.KL'  # 21+1只（DWM信号）
    ]
}

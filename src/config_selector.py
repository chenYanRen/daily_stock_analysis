# -*- coding: utf-8 -*-
"""
===================================
选股配置 - 预设策略和默认参数
===================================

使用方法：
1. 在 .env 中设置 STOCK_SELECTOR_ENABLED=true 启用选股
2. 配置选股策略组合（默认使用均线多头 + MACD 金叉）
3. 设置选股数量（默认每次选出 10 只）

预设策略：
- 激进型：均线多头 + MACD 金叉 + 涨停板
- 稳健型：均线多头 + KDJ 超卖反弹
- 趋势型：放量突破 + 均线多头
- 短线型：涨停板 + KDJ 超卖反弹
"""

from src.services.stock_selector import (
    StockSelectionCriteria,
    SelectionStrategy,
)


# 激进型策略（追求高收益）
AGGRESSIVE_STRATEGY = StockSelectionCriteria(
    ma_bullish=True,
    ma_bullish_days=2,
    macd_golden=True,
    limit_up=True,
    limit_up_days=1,
    top_n=10,
    exclude_st=True,
    price_min=5.0,
    price_max=200.0,
)

# 稳健型策略（追求稳定收益）
STEADY_STRATEGY = StockSelectionCriteria(
    ma_bullish=True,
    ma_bullish_days=3,
    kdj_oversold=True,
    kdj_threshold=20,
    top_n=15,
    exclude_st=True,
    price_min=5.0,
    price_max=300.0,
)

# 趋势型策略（追涨杀跌）
TREND_STRATEGY = StockSelectionCriteria(
    ma_bullish=True,
    ma_bullish_days=2,
    volume_breakout=True,
    volume_ratio_min=1.5,
    volume_ratio_max=5.0,
    top_n=12,
    exclude_st=True,
    price_min=3.0,
    price_max=100.0,
)

# 短线型策略（追求短期波动）
SHORT_TERM_STRATEGY = StockSelectionCriteria(
    limit_up=True,
    limit_up_days=1,
    kdj_oversold=True,
    kdj_threshold=30,
    volume_breakout=True,
    volume_ratio_min=2.0,
    volume_ratio_max=8.0,
    top_n=15,
    exclude_st=True,
    price_min=1.0,
    price_max=100.0,
)

# 默认策略
DEFAULT_STRATEGY = AGGRESSIVE_STRATEGY

# 策略名称映射
STRATEGY_MAPPING = {
    'aggressive': AGGRESSIVE_STRATEGY,
    '激进型': AGGRESSIVE_STRATEGY,
    'steady': STEADY_STRATEGY,
    '稳健型': STEADY_STRATEGY,
    'trend': TREND_STRATEGY,
    '趋势型': TREND_STRATEGY,
    'short_term': SHORT_TERM_STRATEGY,
    '短线型': SHORT_TERM_STRATEGY,
}


def get_strategy(name: str = 'default') -> StockSelectionCriteria:
    """
    获取选股策略
    
    Args:
        name: 策略名称，支持：
            - 'aggressive' / '激进型'
            - 'steady' / '稳健型'
            - 'trend' / '趋势型'
            - 'short_term' / '短线型'
            - 'default' / '默认' -> 激进型
    
    Returns:
        StockSelectionCriteria 实例
    """
    if name.lower() in ('default', '默认'):
        return DEFAULT_STRATEGY
    
    return STRATEGY_MAPPING.get(name, DEFAULT_STRATEGY)


# 环境变量配置说明
"""
# 选股功能开关
STOCK_SELECTOR_ENABLED=true

# 选股策略
# 可选值：aggressive（激进型）、steady（稳健型）、trend（趋势型）、short_term（短线型）
STOCK_SELECTOR_STRATEGY=aggressive

# 选股数量（每次选出的股票数量）
STOCK_SELECTOR_TOP_N=10

# 是否将选股结果追加到 STOCK_LIST
# true: 选股结果会加入分析列表
# false: 只输出选股报告，不分析
STOCK_SELECTOR_APPEND_TO_LIST=true

# 选股功能描述
STOCK_SELECTOR_DESC=均线多头 + MACD金叉

# 自定义选股条件（高级）
# 格式：JSON 字符串
# STOCK_SELECTOR_CRITERIA={"ma_bullish":true,"macd_golden":true,"top_n":10}
"""

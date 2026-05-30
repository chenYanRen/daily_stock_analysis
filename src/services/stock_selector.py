# -*- coding: utf-8 -*-
"""
===================================
选股服务 - 技术指标筛选
===================================

功能：
1. 基于技术指标的选股策略（均线多头、MACD金叉、KDJ超卖等）
2. 涨停板选股
3. 板块热点选股
4. 支持自定义选股条件

选股策略：
- 均线多头排列（MA5 > MA10 > MA20）
- MACD 金叉
- KDJ 超卖反弹
- 放量突破
- 涨停板
- 板块轮动
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class SelectionStrategy(Enum):
    """选股策略类型"""
    MA_BULLISH = "ma_bullish"  # 均线多头排列
    MACD_GOLDEN = "macd_golden"  # MACD 金叉
    KDJ_OVERSOLD = "kdj_oversold"  # KDJ 超卖反弹
    VOLUME_BREAKOUT = "volume_breakout"  # 放量突破
    LIMIT_UP = "limit_up"  # 涨停板
    SECTOR_HOT = "sector_hot"  # 板块热点


@dataclass
class StockSelectionCriteria:
    """选股条件配置"""
    # 均线策略
    ma_bullish: bool = False  # 均线多头排列
    ma_bullish_days: int = 3  # 多头排列持续天数
    
    # MACD 策略
    macd_golden: bool = False  # MACD 金叉
    macd_diff_threshold: float = 0.0  # DIF 值阈值
    
    # KDJ 策略
    kdj_oversold: bool = False  # KDJ 超卖反弹
    kdj_threshold: int = 20  # J 值低于此值视为超卖
    
    # 放量策略
    volume_breakout: bool = False  # 放量突破
    volume_ratio_min: float = 1.5  # 最小放量倍数
    volume_ratio_max: float = 10.0  # 最大放量倍数（避免异常放量）
    
    # 涨停策略
    limit_up: bool = False  # 涨停板选股
    limit_up_days: int = 1  # 连续涨停天数
    
    # 基础筛选
    price_min: float = 1.0  # 最低股价
    price_max: float = 500.0  # 最高股价
    exclude_st: bool = True  # 排除 ST 股
    
    # 返回数量
    top_n: int = 20  # 返回前 N 只股票


@dataclass
class SelectedStock:
    """选中的股票"""
    code: str
    name: str
    score: float  # 综合评分
    reasons: List[str] = field(default_factory=list)  # 入选原因
    indicators: Dict[str, Any] = field(default_factory=dict)  # 关键指标


class TechnicalIndicators:
    """技术指标计算器"""
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算 MACD 指标"""
        df = df.copy()
        
        # 计算 EMA
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        
        # DIF = EMA(fast) - EMA(slow)
        df['macd_dif'] = ema_fast - ema_slow
        
        # DEA = EMA(DIF, signal)
        df['macd_dea'] = df['macd_dif'].ewm(span=signal, adjust=False).mean()
        
        # MACD 柱 = (DIF - DEA) * 2
        df['macd_hist'] = (df['macd_dif'] - df['macd_dea']) * 2
        
        return df
    
    @staticmethod
    def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """计算 KDJ 指标"""
        df = df.copy()
        
        # 计算 RSV
        low_n = df['low'].rolling(window=n, min_periods=1).min()
        high_n = df['high'].rolling(window=n, min_periods=1).max()
        
        rsv = (df['close'] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)
        
        # 计算 K, D, J
        df['kdj_k'] = rsv.ewm(com=m1-1, adjust=False).mean()
        df['kdj_d'] = df['kdj_k'].ewm(com=m2-1, adjust=False).mean()
        df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']
        
        return df
    
    @staticmethod
    def detect_ma_bullish(df: pd.DataFrame, days: int = 1) -> Tuple[bool, int]:
        """
        检测均线多头排列
        
        Returns:
            (是否多头排列, 持续天数)
        """
        if len(df) < days + 1:
            return False, 0
        
        df = df.tail(days + 1)
        
        bullish_days = 0
        for i in range(len(df) - 1, -1, -1):
            row = df.iloc[i]
            if row['ma5'] > row['ma10'] > row['ma20']:
                bullish_days += 1
            else:
                break
        
        return bullish_days >= days, bullish_days
    
    @staticmethod
    def detect_macd_golden_cross(df: pd.DataFrame) -> Tuple[bool, float]:
        """
        检测 MACD 金叉（DIF 从下向上穿越 DEA）
        
        Returns:
            (是否金叉, DIF 值)
        """
        if len(df) < 2:
            return False, 0.0
        
        # 取最近两天
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # 金叉：DIF 上穿 DEA
        golden = (previous['macd_dif'] <= previous['macd_dea'] and 
                  current['macd_dif'] > current['macd_dea'])
        
        return golden, current['macd_dif']
    
    @staticmethod
    def detect_kdj_oversold_rebound(df: pd.DataFrame, threshold: int = 20) -> Tuple[bool, float, float]:
        """
        检测 KDJ 超卖反弹（J 值从超卖区回升）
        
        Returns:
            (是否反弹, J 值, K 值)
        """
        if len(df) < 3:
            return False, 50.0, 50.0
        
        # 取最近三天
        current = df.iloc[-1]
        prev1 = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        # 超卖反弹条件：J 值低于 threshold，然后连续回升
        oversold = prev2['kdj_j'] < threshold
        rebounding = prev1['kdj_j'] > prev2['kdj_j'] and current['kdj_j'] > prev1['kdj_j']
        
        return oversold and rebounding, current['kdj_j'], current['kdj_k']
    
    @staticmethod
    def detect_volume_breakout(df: pd.DataFrame, ratio_min: float = 1.5, ratio_max: float = 10.0) -> Tuple[bool, float]:
        """
        检测放量突破
        
        Returns:
            (是否放量突破, 放量倍数)
        """
        if len(df) < 6:
            return False, 1.0
        
        # 取最近几天
        recent = df.tail(5)
        current = df.iloc[-1]
        
        # 计算 5 日均量
        avg_volume_5 = recent['volume'].iloc[:-1].mean()
        
        if avg_volume_5 <= 0:
            return False, 1.0
        
        volume_ratio = current['volume'] / avg_volume_5
        
        # 放量条件：成交量放大且价格在上涨
        price_up = current['close'] > recent['close'].iloc[-2]
        
        return (ratio_min <= volume_ratio <= ratio_max) and price_up, volume_ratio


class StockSelector:
    """选股服务"""
    
    def __init__(self, data_manager=None):
        """
        初始化选股服务
        
        Args:
            data_manager: DataFetcherManager 实例
        """
        self.data_manager = data_manager
        self.indicators = TechnicalIndicators()
    
    def select_stocks(
        self,
        strategy: SelectionStrategy,
        criteria: StockSelectionCriteria,
        stock_pool: Optional[List[str]] = None,
        sector: Optional[str] = None
    ) -> List[SelectedStock]:
        """
        执行选股
        
        Args:
            strategy: 选股策略
            criteria: 选股条件
            stock_pool: 股票池（None 表示从市场筛选）
            sector: 板块名称（用于板块选股）
            
        Returns:
            选中的股票列表
        """
        logger.info(f"开始选股: 策略={strategy.value}, 条件={criteria}")
        
        start_time = time.time()
        
        try:
            if strategy == SelectionStrategy.MA_BULLISH:
                results = self._select_ma_bullish(criteria, stock_pool)
            elif strategy == SelectionStrategy.MACD_GOLDEN:
                results = self._select_macd_golden(criteria, stock_pool)
            elif strategy == SelectionStrategy.KDJ_OVERSOLD:
                results = self._select_kdj_oversold(criteria, stock_pool)
            elif strategy == SelectionStrategy.VOLUME_BREAKOUT:
                results = self._select_volume_breakout(criteria, stock_pool)
            elif strategy == SelectionStrategy.LIMIT_UP:
                results = self._select_limit_up(criteria, stock_pool)
            elif strategy == SelectionStrategy.SECTOR_HOT:
                results = self._select_sector_hot(criteria, sector)
            else:
                logger.warning(f"未知策略: {strategy}")
                return []
            
            elapsed = time.time() - start_time
            logger.info(f"选股完成: 策略={strategy.value}, 选中={len(results)}只, 耗时={elapsed:.2f}秒")
            
            return results
            
        except Exception as e:
            logger.error(f"选股失败: {e}")
            return []
    
    def _get_stock_list(self, stock_pool: Optional[List[str]] = None) -> List[str]:
        """获取股票列表"""
        if stock_pool:
            return stock_pool
        
        # 如果没有指定股票池，返回默认的自选股列表
        from src.config import get_config
        config = get_config()
        return config.stock_list
    
    def _filter_basic_conditions(self, code: str, quote: Any) -> bool:
        """基础条件过滤"""
        if quote is None:
            return False
        
        name = getattr(quote, 'name', '') or ''
        price = getattr(quote, 'price', 0) or 0
        
        # 排除 ST 股
        if 'ST' in name or '*ST' in name or 'S*ST' in name:
            return False
        
        # 价格范围过滤
        if price < 1.0 or price > 500.0:
            return False
        
        return True
    
    def _select_ma_bullish(self, criteria: StockSelectionCriteria, stock_pool: Optional[List[str]]) -> List[SelectedStock]:
        """均线多头排列选股"""
        results = []
        stock_list = self._get_stock_list(stock_pool)
        
        for code in stock_list:
            try:
                # 获取数据
                df, _ = self.data_manager.get_daily_data(code, days=30)
                
                if df is None or len(df) < 25:
                    continue
                
                # 计算均线
                df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
                df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
                df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
                
                # 检测均线多头
                is_bullish, days = self.indicators.detect_ma_bullish(df, criteria.ma_bullish_days)
                
                if is_bullish:
                    quote = self.data_manager.get_realtime_quote(code)
                    
                    if not self._filter_basic_conditions(code, quote):
                        continue
                    
                    name = getattr(quote, 'name', code)
                    current_price = getattr(quote, 'price', df['close'].iloc[-1])
                    change_pct = getattr(quote, 'change_pct', 0) or 0
                    
                    # 计算评分
                    score = days * 10 + min(change_pct, 10)
                    
                    stock = SelectedStock(
                        code=code,
                        name=name,
                        score=score,
                        reasons=[f"均线多头排列持续{days}天"],
                        indicators={
                            'ma5': round(df['ma5'].iloc[-1], 2),
                            'ma10': round(df['ma10'].iloc[-1], 2),
                            'ma20': round(df['ma20'].iloc[-1], 2),
                            'current_price': current_price,
                            'change_pct': change_pct,
                        }
                    )
                    results.append(stock)
                    
            except Exception as e:
                logger.debug(f"处理 {code} 时出错: {e}")
                continue
        
        # 按评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:criteria.top_n]
    
    def _select_macd_golden(self, criteria: StockSelectionCriteria, stock_pool: Optional[List[str]]) -> List[SelectedStock]:
        """MACD 金叉选股"""
        results = []
        stock_list = self._get_stock_list(stock_pool)
        
        for code in stock_list:
            try:
                df, _ = self.data_manager.get_daily_data(code, days=40)
                
                if df is None or len(df) < 30:
                    continue
                
                # 计算 MACD
                df = self.indicators.calculate_macd(df)
                
                # 检测金叉
                is_golden, dif_value = self.indicators.detect_macd_golden_cross(df)
                
                if is_golden and dif_value >= criteria.macd_diff_threshold:
                    quote = self.data_manager.get_realtime_quote(code)
                    
                    if not self._filter_basic_conditions(code, quote):
                        continue
                    
                    name = getattr(quote, 'name', code)
                    current_price = getattr(quote, 'price', df['close'].iloc[-1])
                    change_pct = getattr(quote, 'change_pct', 0) or 0
                    
                    # 评分：DIF 值越高越好
                    score = min(dif_value * 10, 100) + min(change_pct, 10)
                    
                    stock = SelectedStock(
                        code=code,
                        name=name,
                        score=score,
                        reasons=["MACD 金叉形成"],
                        indicators={
                            'macd_dif': round(dif_value, 4),
                            'macd_dea': round(df['macd_dea'].iloc[-1], 4),
                            'macd_hist': round(df['macd_hist'].iloc[-1], 4),
                            'current_price': current_price,
                            'change_pct': change_pct,
                        }
                    )
                    results.append(stock)
                    
            except Exception as e:
                logger.debug(f"处理 {code} 时出错: {e}")
                continue
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:criteria.top_n]
    
    def _select_kdj_oversold(self, criteria: StockSelectionCriteria, stock_pool: Optional[List[str]]) -> List[SelectedStock]:
        """KDJ 超卖反弹选股"""
        results = []
        stock_list = self._get_stock_list(stock_pool)
        
        for code in stock_list:
            try:
                df, _ = self.data_manager.get_daily_data(code, days=20)
                
                if df is None or len(df) < 15:
                    continue
                
                # 计算 KDJ
                df = self.indicators.calculate_kdj(df)
                
                # 检测超卖反弹
                is_rebound, j_value, k_value = self.indicators.detect_kdj_oversold_rebound(df, criteria.kdj_threshold)
                
                if is_rebound:
                    quote = self.data_manager.get_realtime_quote(code)
                    
                    if not self._filter_basic_conditions(code, quote):
                        continue
                    
                    name = getattr(quote, 'name', code)
                    current_price = getattr(quote, 'price', df['close'].iloc[-1])
                    change_pct = getattr(quote, 'change_pct', 0) or 0
                    
                    # 反弹力度评分
                    score = (50 - j_value) * 2 + min(change_pct, 20)
                    
                    stock = SelectedStock(
                        code=code,
                        name=name,
                        score=score,
                        reasons=[f"KDJ 超卖反弹 (J={j_value:.1f})"],
                        indicators={
                            'kdj_k': round(k_value, 2),
                            'kdj_d': round(df['kdj_d'].iloc[-1], 2),
                            'kdj_j': round(j_value, 2),
                            'current_price': current_price,
                            'change_pct': change_pct,
                        }
                    )
                    results.append(stock)
                    
            except Exception as e:
                logger.debug(f"处理 {code} 时出错: {e}")
                continue
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:criteria.top_n]
    
    def _select_volume_breakout(self, criteria: StockSelectionCriteria, stock_pool: Optional[List[str]]) -> List[SelectedStock]:
        """放量突破选股"""
        results = []
        stock_list = self._get_stock_list(stock_pool)
        
        for code in stock_list:
            try:
                df, _ = self.data_manager.get_daily_data(code, days=10)
                
                if df is None or len(df) < 6:
                    continue
                
                # 计算量比
                df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
                avg_volume_5 = df['volume'].rolling(window=5, min_periods=1).mean()
                df['volume_ratio'] = df['volume'] / avg_volume_5.shift(1)
                
                # 检测放量突破
                is_breakout, ratio = self.indicators.detect_volume_breakout(
                    df, 
                    criteria.volume_ratio_min, 
                    criteria.volume_ratio_max
                )
                
                if is_breakout:
                    quote = self.data_manager.get_realtime_quote(code)
                    
                    if not self._filter_basic_conditions(code, quote):
                        continue
                    
                    name = getattr(quote, 'name', code)
                    current_price = getattr(quote, 'price', df['close'].iloc[-1])
                    change_pct = getattr(quote, 'change_pct', 0) or 0
                    
                    # 放量强度评分
                    score = ratio * 10 + min(change_pct, 15)
                    
                    stock = SelectedStock(
                        code=code,
                        name=name,
                        score=score,
                        reasons=[f"放量突破 (量比={ratio:.2f})"],
                        indicators={
                            'volume_ratio': round(ratio, 2),
                            'volume': int(df['volume'].iloc[-1]),
                            'avg_volume': int(avg_volume_5.iloc[-2]),
                            'current_price': current_price,
                            'change_pct': change_pct,
                            'ma5': round(df['ma5'].iloc[-1], 2),
                        }
                    )
                    results.append(stock)
                    
            except Exception as e:
                logger.debug(f"处理 {code} 时出错: {e}")
                continue
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:criteria.top_n]
    
    def _select_limit_up(self, criteria: StockSelectionCriteria, stock_pool: Optional[List[str]]) -> List[SelectedStock]:
        """涨停板选股"""
        results = []
        
        try:
            # 从数据管理器获取涨停池
            limit_up_list = self.data_manager.get_limit_up_pool(n=50)
            
            if not limit_up_list:
                logger.warning("未获取到涨停板数据")
                return results
            
            for item in limit_up_list:
                try:
                    code = item.get('code', '')
                    name = item.get('name', code)
                    
                    # 基础过滤
                    if not self._filter_basic_conditions(code, None):
                        continue
                    
                    change_pct = item.get('change_pct', 0) or 0
                    
                    # 涨停板
                    if change_pct >= 9.9:  # 接近涨停
                        stock = SelectedStock(
                            code=code,
                            name=name,
                            score=change_pct * 10,
                            reasons=["涨停板"],
                            indicators={
                                'change_pct': change_pct,
                                'volume': item.get('volume', 0),
                                'turnover_rate': item.get('turnover_rate', 0),
                            }
                        )
                        results.append(stock)
                        
                except Exception as e:
                    logger.debug(f"处理涨停股票时出错: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"获取涨停池失败: {e}")
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:criteria.top_n]
    
    def _select_sector_hot(self, criteria: StockSelectionCriteria, sector: Optional[str] = None) -> List[SelectedStock]:
        """板块热点选股"""
        results = []
        
        try:
            # 获取板块排行
            top_sectors, bottom_sectors = self.data_manager.get_sector_rankings(5)
            
            if not top_sectors:
                logger.warning("未获取到板块排行数据")
                return results
            
            # 选择热门板块
            sectors_to_check = top_sectors[:3] if not sector else [s for s in top_sectors if sector in str(s.get('name', ''))]
            
            for sector_data in sectors_to_check:
                sector_name = sector_data.get('name', '未知板块')
                change_pct = sector_data.get('change_pct', 0) or 0
                
                # 获取板块内股票（这里简化处理，实际应通过板块成分股获取）
                # 由于获取板块成分股较复杂，这里仅返回板块信息
                logger.info(f"热门板块: {sector_name}, 涨跌幅: {change_pct}%")
                
        except Exception as e:
            logger.error(f"获取板块热点失败: {e}")
        
        return results
    
    def combined_selection(self, criteria: StockSelectionCriteria, stock_pool: Optional[List[str]] = None) -> List[SelectedStock]:
        """
        综合选股（多种策略组合）
        
        策略优先级：
        1. 均线多头 + MACD 金叉
        2. 涨停板
        3. 放量突破 + KDJ
        """
        all_results = {}
        
        # 1. 均线多头排列
        if criteria.ma_bullish:
            ma_stocks = self._select_ma_bullish(criteria, stock_pool)
            for stock in ma_stocks:
                all_results[stock.code] = stock
        
        # 2. MACD 金叉
        if criteria.macd_golden:
            macd_stocks = self._select_macd_golden(criteria, stock_pool)
            for stock in macd_stocks:
                if stock.code in all_results:
                    all_results[stock.code].reasons.extend(stock.reasons)
                    all_results[stock.code].score += 20
                else:
                    all_results[stock.code] = stock
        
        # 3. 涨停板
        if criteria.limit_up:
            limit_stocks = self._select_limit_up(criteria, stock_pool)
            for stock in limit_stocks:
                if stock.code in all_results:
                    all_results[stock.code].reasons.extend(stock.reasons)
                    all_results[stock.code].score += 30
                else:
                    all_results[stock.code] = stock
        
        # 4. 放量突破
        if criteria.volume_breakout:
            vol_stocks = self._select_volume_breakout(criteria, stock_pool)
            for stock in vol_stocks:
                if stock.code in all_results:
                    all_results[stock.code].reasons.extend(stock.reasons)
                    all_results[stock.code].score += 15
                else:
                    all_results[stock.code] = stock
        
        # 排序并返回
        results = list(all_results.values())
        results.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"综合选股完成: 共选中 {len(results)} 只股票")
        return results[:criteria.top_n]
    
    def format_selection_report(self, stocks: List[SelectedStock]) -> str:
        """格式化选股报告"""
        if not stocks:
            return "今日无符合条件的股票"
        
        lines = [
            f"📊 智能选股结果（共 {len(stocks)} 只）",
            "=" * 50,
        ]
        
        for i, stock in enumerate(stocks, 1):
            lines.append(f"\n{i}. {stock.name}({stock.code})")
            lines.append(f"   评分: {stock.score:.1f}")
            lines.append(f"   原因: {' | '.join(stock.reasons)}")
            
            # 显示关键指标
            ind = stock.indicators
            if 'current_price' in ind:
                lines.append(f"   价格: {ind['current_price']:.2f}")
            if 'change_pct' in ind:
                lines.append(f"   涨幅: {ind['change_pct']:+.2f}%")
        
        return "\n".join(lines)

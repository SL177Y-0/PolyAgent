"""Strategy interface for trading decisions.

This module provides an abstract Strategy base class that allows for:
1. Clean separation of strategy logic from bot orchestration
2. Easy strategy swapping at runtime
3. Future LLM integration (Task Requirement §5)

The strategy function signature follows the task specification:
    decide_action(event, market_state, config) → decision
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

from .config import Config

logger = logging.getLogger(__name__)


class Strategy(ABC):
    """Abstract base class for trading strategies.
    
    Designed for LLM extensibility per Task Requirement §5:
    "Strategy logic must be encapsulated in a single decision function"
    "This is required so that LLM support can be added later as a simple function extension"
    """
    
    @abstractmethod
    def decide_action(
        self,
        event: Dict[str, Any],
        market_state: Dict[str, Any],
        config: Config
    ) -> Dict[str, Any]:
        """Make a trading decision based on event and market state.
        
        Args:
            event: Event data containing:
                - spike_pct: float - Detected spike percentage
                - direction: str - "up" or "down" or "none"
                - window_seconds: int - Detection window in seconds
                - volatility_cv: float - Coefficient of variation
                
            market_state: Current market conditions:
                - price: float - Current price
                - has_position: bool - Whether a position is open
                - position_type: str - "LONG", "SHORT", or None
                - initial_inventory_acquired: bool - Session started with buy
                - in_cooldown: bool - Whether in cooldown period
                
            config: Configuration object with thresholds
                
        Returns:
            Dict with decision:
                - action: "buy" | "sell" | "ignore"
                - size_usd: float (trade size in USD)
                - reason: str (explanation for logging)
        """
        pass
    
    @property
    def name(self) -> str:
        """Strategy name for logging."""
        return self.__class__.__name__


class SpikeSamStrategy(Strategy):
    """Spike Sam Fade Strategy: Fade price spikes.
    
    Strategy Logic:
    1. Session Start: BUY to establish initial inventory
    2. After inventory acquired:
       - Spike UP → SELL (fade the pump, take profit)
       - Spike DOWN → BUY (fade the dump, add inventory)
    
    This implements the exact strategy specified in Task Requirement §5:
    "Spike UP → sell, Spike DOWN → buy, Ignore weak or noisy spikes"
    """
    
    def __init__(self, max_inventory_size_usd: Optional[float] = None):
        """Initialize SpikeSamStrategy.
        
        Args:
            max_inventory_size_usd: Maximum inventory size limit (None = no limit)
        """
        self.max_inventory_size_usd = max_inventory_size_usd
    
    def decide_action(
        self,
        event: Dict[str, Any],
        market_state: Dict[str, Any],
        config: Config
    ) -> Dict[str, Any]:
        """Implement Spike Sam fade strategy."""
        
        spike_pct = event.get("spike_pct", 0.0)
        has_position = market_state.get("has_position", False)
        in_cooldown = market_state.get("in_cooldown", False)
        initial_inventory_acquired = market_state.get("initial_inventory_acquired", False)
        current_inventory_usd = market_state.get("current_inventory_usd", 0.0)
        volatility_filtered = event.get("volatility_filtered", False)
        
        # If we have a position, ignore (risk exits handle TP/SL)
        if has_position:
            return {"action": "ignore", "size_usd": 0, "reason": "position_open"}
        
        # In cooldown
        if in_cooldown:
            return {"action": "ignore", "size_usd": 0, "reason": "cooldown"}
        
        # PRIORITY: Initial inventory acquisition (session start)
        # Must happen BEFORE volatility filter to ensure we can always get initial position
        if not initial_inventory_acquired:
            logger.info("[STRATEGY] Session start - acquiring initial inventory with BUY")
            return {
                "action": "buy",
                "size_usd": config.default_trade_size_usd,
                "reason": "initial_inventory_acquisition"
            }
        
        # Check volatility filter (only after initial inventory)
        if volatility_filtered:
            return {
                "action": "ignore",
                "size_usd": 0,
                "reason": f"volatility_filtered ({event.get('volatility_reason', 'high CV')})"
            }
        
        # Calculate effective threshold
        threshold = config.spike_threshold_pct
        min_strength = config.min_spike_strength
        effective_threshold = max(threshold, abs(min_strength))
        
        # Spike UP → SELL (fade the pump)
        if spike_pct >= effective_threshold:
            return {
                "action": "sell",
                "size_usd": config.default_trade_size_usd,
                "reason": f"spike_up_{spike_pct:.2f}%_window_{event.get('window_seconds', 'unknown')}s"
            }
        
        # Spike DOWN → BUY (fade the dump, add inventory)
        if spike_pct <= -effective_threshold:
            # Check inventory limit
            max_inv = self.max_inventory_size_usd or getattr(config, 'max_inventory_size_usd', None)
            if max_inv and max_inv > 0 and current_inventory_usd >= max_inv:
                logger.info(
                    f"[STRATEGY] Inventory limit reached: "
                    f"${current_inventory_usd:.2f} >= ${max_inv:.2f}"
                )
                return {"action": "ignore", "size_usd": 0, "reason": "inventory_limit_reached"}
            
            return {
                "action": "buy",
                "size_usd": config.default_trade_size_usd,
                "reason": f"spike_down_{abs(spike_pct):.2f}%_window_{event.get('window_seconds', 'unknown')}s"
            }
        
        # No significant spike
        return {"action": "ignore", "size_usd": 0, "reason": "no_spike"}


def create_strategy(strategy_type: str = "spike_sam", **kwargs) -> Strategy:
    """Factory function to create strategy instances.
    
    This factory pattern allows easy extension for future strategies:
    - LLM-based strategy
    - Momentum strategy
    - Mean reversion strategy
    
    Args:
        strategy_type: Type of strategy to create
        **kwargs: Additional arguments passed to strategy constructor
        
    Returns:
        Strategy instance
        
    Raises:
        ValueError: If strategy_type is unknown
    """
    strategies = {
        "spike_sam": SpikeSamStrategy,
        # Future: "llm": LLMStrategy,
        # Future: "momentum": MomentumStrategy,
    }
    
    if strategy_type not in strategies:
        raise ValueError(f"Unknown strategy type: {strategy_type}. Available: {list(strategies.keys())}")
    
    return strategies[strategy_type](**kwargs)

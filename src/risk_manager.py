"""Risk management system with comprehensive safety checks"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RiskCheckResult:
    """Result of risk validation"""
    
    def __init__(self, passed: bool, reasons: List[str] = None):
        self.passed = passed
        self.reasons = reasons or []
        self.timestamp = datetime.now()
    
    def add_reason(self, reason: str):
        """Add a failure reason"""
        self.reasons.append(reason)
        self.passed = False
    
    def __bool__(self):
        return self.passed
    
    def __repr__(self):
        status = "PASSED" if self.passed else "FAILED"
        reasons_str = ", ".join(self.reasons) if self.reasons else "All checks passed"
        return f"RiskCheck({status}: {reasons_str})"


class RiskManager:
    """
    Comprehensive risk management system
    Enforces trading limits and safety rules
    """
    
    def __init__(
        self,
        min_size_usd: float = 1.0,
        max_size_usd: float = 100.0,
        max_positions: int = 1,
        max_hold_minutes: int = 60,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        daily_loss_limit_usd: Optional[float] = None
    ):
        """
        Initialize risk manager
        
        Args:
            min_size_usd: Minimum trade size in USD
            max_size_usd: Maximum trade size in USD
            max_positions: Maximum concurrent positions
            max_hold_minutes: Maximum holding time in minutes
            stop_loss_pct: Stop-loss percentage (optional)
            take_profit_pct: Take-profit percentage (optional)
            daily_loss_limit_usd: Daily loss limit in USD (optional)
        """
        self.min_size_usd = min_size_usd
        self.max_size_usd = max_size_usd
        self.max_positions = max_positions
        self.max_hold_minutes = max_hold_minutes
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_loss_limit_usd = daily_loss_limit_usd
        
        # Track daily P&L
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Statistics
        self.checks_performed = 0
        self.checks_passed = 0
        self.checks_failed = 0
    
    def validate_trade(
        self,
        size_usd: float,
        current_positions: Dict[str, Any],
        market_id: str
    ) -> RiskCheckResult:
        """
        Validate a trade against all risk rules
        
        Args:
            size_usd: Proposed trade size in USD
            current_positions: Dictionary of current positions
            market_id: Market ID for the trade
        
        Returns:
            RiskCheckResult with pass/fail and reasons
        """
        self.checks_performed += 1
        result = RiskCheckResult(passed=True)
        
        # Check 1: Trade size within limits
        if not self._check_trade_size(size_usd, result):
            pass
        
        # Check 2: Max positions limit
        if not self._check_max_positions(current_positions, market_id, result):
            pass
        
        # Check 3: Daily loss limit
        if not self._check_daily_loss_limit(result):
            pass
        
        # Update statistics
        if result.passed:
            self.checks_passed += 1
        else:
            self.checks_failed += 1
        
        return result
    
    def _check_trade_size(self, size_usd: float, result: RiskCheckResult) -> bool:
        """Check if trade size is within limits"""
        if size_usd < self.min_size_usd:
            result.add_reason(
                f"Trade size ${size_usd:.2f} below minimum ${self.min_size_usd:.2f}"
            )
            return False
        
        if size_usd > self.max_size_usd:
            result.add_reason(
                f"Trade size ${size_usd:.2f} exceeds maximum ${self.max_size_usd:.2f}"
            )
            return False
        
        return True
    
    def _check_max_positions(
        self,
        current_positions: Dict[str, Any],
        market_id: str,
        result: RiskCheckResult
    ) -> bool:
        """Check if max positions limit would be exceeded"""
        # Count non-flat positions
        open_positions = sum(
            1 for pos in current_positions.values()
            if pos.get('position_type') != 'FLAT'
        )
        
        # Check if market already has open position
        if market_id in current_positions:
            existing_pos = current_positions[market_id]
            if existing_pos.get('position_type') != 'FLAT':
                result.add_reason(
                    f"Market {market_id} already has open position: {existing_pos['position_type']}"
                )
                return False
        elif open_positions >= self.max_positions:
            result.add_reason(
                f"Max positions limit reached: {open_positions}/{self.max_positions}"
            )
            return False
        
        return True
    
    def _check_daily_loss_limit(self, result: RiskCheckResult) -> bool:
        """Check if daily loss limit has been exceeded"""
        # Reset daily P&L if new day
        self._reset_daily_pnl_if_needed()
        
        if self.daily_loss_limit_usd is None:
            return True
        
        if self.daily_pnl < -self.daily_loss_limit_usd:
            result.add_reason(
                f"Daily loss limit exceeded: ${self.daily_pnl:.2f} / -${self.daily_loss_limit_usd:.2f}"
            )
            return False
        
        return True
    
    def should_close_position(
        self,
        position: Dict[str, Any],
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Check if position should be closed based on risk rules
        
        Args:
            position: Position dictionary
            current_price: Current market price
        
        Returns:
            Tuple of (should_close, reason)
        """
        # Check 1: Max holding time
        if self._check_holding_time_exceeded(position):
            return True, "Maximum holding time exceeded"
        
        # Check 2: Stop-loss
        if self._check_stop_loss(position, current_price):
            return True, "Stop-loss triggered"
        
        # Check 3: Take-profit
        if self._check_take_profit(position, current_price):
            return True, "Take-profit target reached"
        
        return False, ""
    
    def _check_holding_time_exceeded(self, position: Dict[str, Any]) -> bool:
        """Check if position has been held too long"""
        entry_time = position.get('entry_time')
        if not entry_time:
            return False
        
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time)
        
        holding_time = (datetime.now() - entry_time).total_seconds() / 60
        
        return holding_time >= self.max_hold_minutes
    
    def _check_stop_loss(self, position: Dict[str, Any], current_price: float) -> bool:
        """Check if stop-loss has been hit"""
        if self.stop_loss_pct is None:
            return False
        
        entry_price = position.get('entry_price')
        position_type = position.get('position_type')
        
        if not entry_price or position_type == 'FLAT':
            return False
        
        # Calculate unrealized P&L percentage
        if position_type == 'LONG':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        # Check if loss exceeds stop-loss
        return pnl_pct <= -self.stop_loss_pct
    
    def _check_take_profit(self, position: Dict[str, Any], current_price: float) -> bool:
        """Check if take-profit target has been reached"""
        if self.take_profit_pct is None:
            return False
        
        entry_price = position.get('entry_price')
        position_type = position.get('position_type')
        
        if not entry_price or position_type == 'FLAT':
            return False
        
        # Calculate unrealized P&L percentage
        if position_type == 'LONG':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl_pct = ((entry_price - current_price) / entry_price) * 100
        
        # Check if profit exceeds take-profit
        return pnl_pct >= self.take_profit_pct
    
    def record_trade_pnl(self, pnl: float):
        """Record realized P&L for daily tracking"""
        self._reset_daily_pnl_if_needed()
        self.daily_pnl += pnl
        logger.info(f"Daily P&L updated: ${self.daily_pnl:.2f}")
    
    def _reset_daily_pnl_if_needed(self):
        """Reset daily P&L if it's a new day"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            logger.info(f"New day - resetting daily P&L (was ${self.daily_pnl:.2f})")
            self.daily_pnl = 0.0
            self.last_reset_date = today
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get risk manager statistics"""
        self._reset_daily_pnl_if_needed()
        
        return {
            'checks_performed': self.checks_performed,
            'checks_passed': self.checks_passed,
            'checks_failed': self.checks_failed,
            'pass_rate': (self.checks_passed / self.checks_performed * 100) if self.checks_performed > 0 else 0,
            'daily_pnl': self.daily_pnl,
            'daily_loss_limit': self.daily_loss_limit_usd,
            'limits': {
                'min_size_usd': self.min_size_usd,
                'max_size_usd': self.max_size_usd,
                'max_positions': self.max_positions,
                'max_hold_minutes': self.max_hold_minutes,
                'stop_loss_pct': self.stop_loss_pct,
                'take_profit_pct': self.take_profit_pct
            }
        }
    
    def reset_statistics(self):
        """Reset statistics (but keep daily P&L)"""
        self.checks_performed = 0
        self.checks_passed = 0
        self.checks_failed = 0


def create_risk_manager(config: Dict[str, Any]) -> RiskManager:
    """
    Factory function to create RiskManager from config
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Initialized RiskManager instance
    """
    risk_config = config['risk_limits']
    
    manager = RiskManager(
        min_size_usd=risk_config.get('min_size_usd', 1.0),
        max_size_usd=risk_config.get('max_size_usd', 100.0),
        max_positions=risk_config.get('max_positions', 1),
        max_hold_minutes=risk_config.get('max_hold_minutes', 60),
        stop_loss_pct=risk_config.get('stop_loss_pct'),
        take_profit_pct=risk_config.get('take_profit_pct'),
        daily_loss_limit_usd=risk_config.get('daily_loss_limit_usd')
    )
    
    logger.info("Risk manager initialized with limits")
    
    return manager

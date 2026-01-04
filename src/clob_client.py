"""CLOB client wrapper with dual-mode (EOA/Proxy) support and helpers.

Uses py-clob-client under the hood. Provides:
- resolve_token_id: resolve MARKET_SLUG to token id (cached), or use MARKET_TOKEN_ID
- get_mid_price: compute best-bid/ask mid from orderbook
- place_market_order: post a market order (FOK) using USD amount
- check_orderbook_health: validate liquidity before trading
- get_smart_price: get realistic price with slippage tolerance

This implementation intentionally avoids extra complexity (limit orders, share math)
and follows the known-good pattern: MarketOrderArgs + create_market_order + post_order(FOK).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

import requests
from py_clob_client.client import ClobClient as _ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    success: bool
    response: Dict[str, Any]


class Client:
    def __init__(self, config: Config):
        self.config = config
        self._client = _ClobClient(
            host=config.host,
            key=config.private_key,
            chain_id=config.chain_id,
            signature_type=int(config.signature_type),
            funder=config.funder_address if int(config.signature_type) != 0 else None,
        )
        api_creds = self._client.create_or_derive_api_creds()
        self._client.set_api_creds(api_creds)
        logger.info("API credentials ready")
        self._token_cache: Dict[str, str] = {}

    def resolve_token_id(self, market_index: Optional[int] = None) -> str:
        """Resolve market slug to token ID.

        Args:
            market_index: Which market within the event to use. If None, uses config market_index or finds first active market.

        Returns:
            str: The token ID for the specified market
        """
        if self.config.market_token_id:
            return str(self.config.market_token_id)
        if not self.config.market_slug:
            raise ValueError("Set MARKET_TOKEN_ID or MARKET_SLUG in .env")

        # Use config market_index if provided, otherwise use parameter
        if market_index is None:
            market_index = self.config.market_index

        slug = self.config.market_slug
        cache_key = f"{slug}_{market_index or 0}"
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]

        url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            raise ValueError(f"Market slug not found: {slug}")

        markets = data[0].get("markets", [])
        if not markets:
            raise ValueError(f"No markets found for slug {slug}")

        # Select the market
        if market_index is not None and market_index < len(markets):
            market = markets[market_index]
        else:
            # Find first active, non-closed market
            market = None
            for m in markets:
                if m.get("active", False) and not m.get("closed", True):
                    market = m
                    break
            if not market:
                market = markets[0]

        clob_token_ids = market.get("clobTokenIds", [])
        if isinstance(clob_token_ids, str):
            try:
                clob_token_ids = json.loads(clob_token_ids)
            except Exception:
                pass
        if not clob_token_ids:
            raise ValueError(f"No clobTokenIds for slug {slug}")

        token_id = clob_token_ids[0]  # YES token
        self._token_cache[cache_key] = token_id

        question = market.get("question", "")[:50]
        logger.info(f"Resolved token id for '{question}': {token_id[:40]}...")
        return token_id

    def get_orderbook(self, token_id: Optional[str] = None) -> Dict[str, Any]:
        token = token_id or self.resolve_token_id()
        return self._client.get_order_book(token)

    def get_mid_price(self, token_id: Optional[str] = None) -> float:
        ob = self.get_orderbook(token_id)
        def first_price(side):
            if not side:
                return None
            first = side[0]
            return float(first.price if hasattr(first, "price") else first["price"])  # type: ignore[index]
        # Handle both OrderBookSummary objects and dicts without evaluating .get on non-dicts
        if hasattr(ob, "bids"):
            bids = ob.bids or []
        elif isinstance(ob, dict):
            bids = ob.get("bids", [])
        else:
            bids = []
        if hasattr(ob, "asks"):
            asks = ob.asks or []
        elif isinstance(ob, dict):
            asks = ob.get("asks", [])
        else:
            asks = []
        best_bid = first_price(bids) or 0.0
        best_ask = first_price(asks) or 1.0
        if best_bid > 0 and best_ask < 1:
            return (best_bid + best_ask) / 2.0
        return best_bid or best_ask

    def get_last_trade_price(self, token_id: Optional[str] = None) -> float:
        """Get the most recent trade price from CLOB API.

        This is the price of the last executed trade, used by Polymarket
        as the displayed price when the spread exceeds $0.10.

        Args:
            token_id: The token ID to fetch last trade for

        Returns:
            float: The last trade price, or 0.0 if unavailable
        """
        token = token_id or self.resolve_token_id()
        try:
            result = self._client.get_last_trade_price(str(token))
            price = float(result.get("price", 0))
            if price > 0:
                logger.debug(f"Last trade price: {price:.4f}")
                return price
        except Exception as e:
            logger.debug(f"Failed to fetch last trade price: {e}")
        return 0.0

    def get_polymarket_price(self, token_id: Optional[str] = None) -> float:
        """Get price using Polymarket's official pricing logic.

        Polymarket displays prices as follows:
        - If spread <= 0.10: midpoint of best bid/ask
        - If spread > 0.10: last trade price

        This ensures the bot uses the same prices users see on polymarket.com.

        Args:
            token_id: The token ID to fetch price for

        Returns:
            float: The price according to Polymarket's logic
        """
        token = token_id or self.resolve_token_id()

        # Get orderbook for bid/ask and spread
        ob = self.get_orderbook(token)

        def first_price(side):
            if not side:
                return None
            first = side[0]
            return float(first.price if hasattr(first, "price") else first["price"])

        if hasattr(ob, "bids"):
            bids = ob.bids or []
        elif isinstance(ob, dict):
            bids = ob.get("bids", [])
        else:
            bids = []
        if hasattr(ob, "asks"):
            asks = ob.asks or []
        elif isinstance(ob, dict):
            asks = ob.get("asks", [])
        else:
            asks = []

        best_bid = first_price(bids)
        best_ask = first_price(asks)

        # Need both bid and ask to calculate spread
        if best_bid and best_ask and best_bid > 0 and best_ask > 0:
            spread = best_ask - best_bid

            # Polymarket's official logic:
            # Use midpoint if spread <= 0.10, otherwise use last trade price
            if spread <= 0.10:
                mid = (best_bid + best_ask) / 2.0
                logger.debug(f"Price (spread {spread:.2f} <= 0.10): midpoint = {mid:.4f}")
                return mid
            else:
                # Spread too wide - use last trade price
                last_trade = self.get_last_trade_price(token)
                if last_trade > 0:
                    logger.debug(f"Price (spread {spread:.2f} > 0.10): last_trade = {last_trade:.4f}")
                    return last_trade
                else:
                    # Fallback to midpoint if no last trade available
                    logger.debug(f"Price (spread {spread:.2f} > 0.10, no last trade): midpoint = {(best_bid + best_ask) / 2.0:.4f}")
                    return (best_bid + best_ask) / 2.0

        # Fallback: try last trade price, then best bid
        last_trade = self.get_last_trade_price(token)
        if last_trade > 0:
            return last_trade

        return best_bid or 0.0

    def get_gamma_price(self, token_id: Optional[str] = None, market_index: Optional[int] = None) -> float:
        """Fetch price from Gamma API based on MARKET_SLUG; fallback for display/monitoring.

        Args:
            token_id: Optional token ID to match against clobTokenIds
            market_index: Which market within the event to use (default: use config market_index)

        Returns:
            float: The YES price for the specified market
        """
        slug = self.config.market_slug
        if not slug:
            return 0.0
        # Use config market_index if not specified
        if market_index is None:
            market_index = self.config.market_index
        try:
            url = f"https://gamma-api.polymarket.com/events?slug={slug}"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                logger.debug(f"Gamma API returned {resp.status_code}")
                return 0.0
            data = resp.json()
            if not data:
                return 0.0

            # Get all markets for this event
            markets = data[0].get("markets", [])
            if not markets:
                return 0.0

            # Use the specified market index (or find the first active one)
            market = None
            if market_index is not None and market_index >= 0 and market_index < len(markets):
                # Use the specified index
                market = markets[market_index]
            else:
                # Find first active, non-closed market
                for m in markets:
                    if m.get("active", False) and not m.get("closed", True):
                        market = m
                        break
                if not market and markets:
                    market = markets[0]

            if not market:
                return 0.0

            prices = market.get("outcomePrices", [])
            if not prices:
                return 0.0

            # Parse prices if it's a JSON string
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except json.JSONDecodeError:
                    return 0.0

            # For binary markets, prices[0] is YES price, prices[1] is NO price
            # Return the YES price (first price)
            try:
                price = float(prices[0])
                if price > 0:
                    return price
            except (ValueError, TypeError, IndexError):
                pass

            return 0.0
        except Exception as e:
            logger.debug(f"Gamma API error: {e}")
            return 0.0

    def get_orderbook_metrics(self, token_id: Optional[str] = None) -> Dict[str, float]:
        """Compute simple orderbook metrics for guards."""
        ob = self.get_orderbook(token_id)
        def first_price(side):
            if not side:
                return None
            first = side[0]
            return float(first.price if hasattr(first, "price") else first["price"])  # type: ignore[index]
        def size5(side):
            total = 0.0
            if not side:
                return 0.0
            take = side if isinstance(side, list) else list(side)
            for o in take[:5]:
                s = (o.size if hasattr(o, "size") else o.get("size", 0))  # type: ignore[attr-defined]
                try:
                    total += float(s)
                except Exception:
                    continue
            return total
        if hasattr(ob, "bids"):
            bids = ob.bids or []
        else:
            bids = ob.get("bids", []) if isinstance(ob, dict) else []
        if hasattr(ob, "asks"):
            asks = ob.asks or []
        else:
            asks = ob.get("asks", []) if isinstance(ob, dict) else []
        bb = first_price(bids) or 0.0
        ba = first_price(asks) or 1.0
        spread = (ba - bb) if (bb and ba) else 0.0
        spread_pct = (spread / bb * 100.0) if bb > 0 else 0.0
        return {
            "best_bid": bb,
            "best_ask": ba,
            "spread_pct": spread_pct,
            "bid_liquidity": size5(bids),
            "ask_liquidity": size5(asks),
        }

    def get_balance_allowance(self, token_id: Optional[str] = None) -> Dict[str, Any]:
        token = token_id or self.resolve_token_id()
        try:
            return self._client.get_balance_allowance(token)
        except Exception as e:
            logger.warning(f"Balance/allowance fetch failed: {e}")
            return {}

    def has_sufficient_balance(self, amount_usd: float, token_id: Optional[str] = None) -> Tuple[bool, str]:
        """Check if wallet has sufficient balance for trade.

        Args:
            amount_usd: Trade amount in USD
            token_id: Token ID to check (uses default if None)

        Returns:
            Tuple of (has_balance, message)
        """
        try:
            ba = self.get_balance_allowance(token_id)
            if not ba:
                return False, "Could not fetch balance/allowance"

            # Get available balance (side depends on what we're trading)
            # For YES tokens: balance is in USDC.e collateral
            available_bal = float(ba.get("availableBalance", 0))
            allowance = float(ba.get("allowance", 0))

            # We need both balance AND allowance
            if available_bal < amount_usd:
                return False, f"Insufficient balance: ${available_bal:.2f} < ${amount_usd:.2f}"
            if allowance < amount_usd:
                return False, f"Insufficient allowance: ${allowance:.2f} < ${amount_usd:.2f}"

            return True, f"Balance OK: ${available_bal:.2f}"
        except Exception as e:
            logger.warning(f"Balance check error: {e}")
            return False, f"Balance check failed: {e}"

    def check_orderbook_health(self, side: str, amount_usd: float, token_id: Optional[str] = None,
                              min_liquidity: float = 1.0, max_spread_pct: float = 5.0) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if orderbook has sufficient liquidity for our trade.

        Args:
            side: "BUY" or "SELL"
            amount_usd: Trade amount in USD
            token_id: Token ID to check
            min_liquidity: Minimum liquidity required on the side
            max_spread_pct: Maximum allowed spread percentage

        Returns:
            Tuple of (is_healthy, message, orderbook_info)
        """
        try:
            ob = self.get_orderbook(token_id)

            # Extract bids/asks
            if hasattr(ob, "bids"):
                bids = ob.bids or []
                asks = ob.asks or []
            else:
                bids = ob.get("bids", [])
                asks = ob.get("asks", [])

            if not bids or not asks:
                return False, "Orderbook empty - one or both sides have no orders", {}

            def first_price_and_size(side_data):
                if not side_data:
                    return None, 0.0
                first = side_data[0]
                price = float(first.price if hasattr(first, "price") else first["price"])
                size = float(first.size if hasattr(first, "size") else first.get("size", 0))
                return price, size

            best_bid, bid_size = first_price_and_size(bids)
            best_ask, ask_size = first_price_and_size(asks)

            if best_bid is None or best_ask is None:
                return False, "Cannot determine best bid/ask prices", {}

            # Calculate spread
            spread_pct = (best_ask - best_bid) / best_bid * 100 if best_bid > 0 else 999

            # Check which side we need liquidity on
            if side.upper() == "BUY":
                # We're buying YES tokens -> need ask liquidity
                required_size = amount_usd / best_ask if best_ask > 0 else 0
                if ask_size < required_size:
                    return False, f"Insufficient ask liquidity: ${ask_size*best_ask:.2f} < ${amount_usd:.2f}", {
                        "best_ask": best_ask,
                        "ask_size": ask_size,
                        "spread_pct": spread_pct
                    }
            else:  # SELL
                # We're selling YES tokens -> need bid liquidity
                required_size = amount_usd / best_bid if best_bid > 0 else 0
                if bid_size < required_size:
                    return False, f"Insufficient bid liquidity: ${bid_size*best_bid:.2f} < ${amount_usd:.2f}", {
                        "best_bid": best_bid,
                        "bid_size": bid_size,
                        "spread_pct": spread_pct
                    }

            # Check spread
            if spread_pct > max_spread_pct:
                return False, f"Spread too wide: {spread_pct:.2f}% > {max_spread_pct}%", {
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread_pct": spread_pct
                }

            info = {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_pct": spread_pct,
                "bid_size": bid_size,
                "ask_size": ask_size
            }
            return True, f"Orderbook healthy - spread: {spread_pct:.2f}%", info

        except Exception as e:
            logger.warning(f"Orderbook health check failed: {e}")
            return False, f"Health check failed: {e}", {}

    def get_smart_price(self, side: str, amount_usd: float, token_id: Optional[str] = None,
                       slippage_pct: float = 0.5) -> Optional[float]:
        """Get realistic execution price with slippage consideration.

        For BUY: use best_ask + slippage
        For SELL: use best_bid - slippage

        Args:
            side: "BUY" or "SELL"
            amount_usd: Trade amount (for sizing validation)
            token_id: Token ID
            slippage_pct: Slippage to add/subtract from best price (default 0.5%)

        Returns:
            float: Expected execution price, or None if unavailable
        """
        try:
            ob = self.get_orderbook(token_id)

            if hasattr(ob, "bids"):
                bids = ob.bids or []
                asks = ob.asks or []
            else:
                bids = ob.get("bids", [])
                asks = ob.get("asks", [])

            def first_price(side_data):
                if not side_data:
                    return None
                first = side_data[0]
                return float(first.price if hasattr(first, "price") else first["price"])

            best_bid = first_price(bids)
            best_ask = first_price(asks)

            if side.upper() == "BUY":
                if best_ask is None:
                    return None
                # Add slippage to ask price
                slippage_multiplier = 1 + (slippage_pct / 100)
                return best_ask * slippage_multiplier
            else:  # SELL
                if best_bid is None:
                    return None
                # Subtract slippage from bid price
                slippage_multiplier = 1 - (slippage_pct / 100)
                return best_bid * slippage_multiplier

        except Exception as e:
            logger.debug(f"Smart price calculation failed: {e}")
            return None

    def place_market_order(self, side: str, amount_usd: float, token_id: Optional[str] = None,
                          order_type: OrderType = OrderType.FOK,
                          skip_precheck: bool = False) -> OrderResult:
        """Place a market order with intelligent pre-checks and retry logic.

        Args:
            side: "BUY" or "SELL"
            amount_usd: Trade amount in USD
            token_id: Token ID (uses default if None)
            order_type: Order type (FOK or FAK)
            skip_precheck: Skip balance/orderbook checks (for retries)

        Returns:
            OrderResult with success status and response data

        Raises:
            Exception: If all retry attempts fail
        """
        token = token_id or self.resolve_token_id()

        if self.config.dry_run:
            logger.info(f"DRY-RUN: Would place {side} ${amount_usd:.2f} on {token[:10]}...")
            return OrderResult(True, {"dry_run": True, "side": side, "amount": amount_usd, "token_id": token})

        # Pre-flight checks (only on first attempt)
        if not skip_precheck:
            # 1. Balance check
            has_bal, bal_msg = self.has_sufficient_balance(amount_usd, token)
            if not has_bal:
                logger.warning(f"[PRE_CHECK_FAILED] {bal_msg}")
                return OrderResult(False, {"error": bal_msg, "reason": "insufficient_balance"})

            # 2. Orderbook health check
            is_healthy, health_msg, ob_info = self.check_orderbook_health(
                side, amount_usd, token,
                min_liquidity=self.config.min_bid_liquidity if side.upper() == "SELL" else self.config.min_ask_liquidity,
                max_spread_pct=self.config.max_spread_pct
            )
            if not is_healthy:
                logger.warning(f"[PRE_CHECK_FAILED] {health_msg}")
                return OrderResult(False, {"error": health_msg, "reason": "orderbook_unhealthy", "orderbook": ob_info})

            logger.debug(f"[PRE_CHECK_OK] {bal_msg} | {health_msg}")

        args = MarketOrderArgs(
            token_id=str(token),
            amount=float(amount_usd),
            side=BUY if side.upper() == "BUY" else SELL,
        )

        attempts = 0
        max_attempts = 4
        last_err: Optional[Exception] = None
        last_error_msg = ""

        while attempts < max_attempts:
            try:
                signed = self._client.create_market_order(args)
                resp = self._client.post_order(signed, order_type)
                ok = bool(resp.get("success"))
                if ok:
                    order_id = resp.get('orderID', 'N/A')
                    logger.info(f"[ORDER_FILLED] {order_id}")
                    return OrderResult(True, resp)
                else:
                    err = resp.get("errorMsg", resp.get("error", "Unknown error"))
                    last_error_msg = str(err)

                    # Check for specific error types
                    if "balance" in err.lower() or "allowance" in err.lower():
                        logger.warning(f"[BALANCE_ERROR] {err}")
                        # Don't retry balance errors - they won't fix themselves
                        last_err = RuntimeError(err)
                        break

                    if "no match" in err.lower():
                        # For "no match", check orderbook again and maybe skip this trade
                        logger.warning(f"[NO_MATCH] Attempt {attempts+1}/{max_attempts}")
                        # Short delay before retry
                        time.sleep(0.3)

                    logger.warning(f"Order attempt {attempts+1}/{max_attempts} failed: {err}")
                    last_err = RuntimeError(err)

            except Exception as e:
                err_msg = str(e)
                last_error_msg = err_msg

                # Check for balance/allowance errors in exceptions
                if "balance" in err_msg.lower() or "allowance" in err_msg.lower():
                    logger.warning(f"[BALANCE_ERROR] {e}")
                    last_err = e
                    break

                logger.warning(f"Order attempt {attempts+1}/{max_attempts} exception: {e}")
                last_err = e

            attempts += 1
            # Exponential backoff with jitter
            if attempts < max_attempts:
                sleep_time = 0.2 * (1.5 ** attempts)
                time.sleep(sleep_time)

        # All attempts failed
        assert last_err is not None
        logger.error(f"[ORDER_FAILED] After {max_attempts} attempts: {last_error_msg}")
        raise last_err

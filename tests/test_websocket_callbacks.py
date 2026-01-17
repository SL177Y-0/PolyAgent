
import pytest
import asyncio
import threading
import time
from unittest.mock import MagicMock, AsyncMock
from src.bot_session import BotSession, BotConfigData

@pytest.fixture
def mock_session():
    config_data = BotConfigData(
        bot_id="test_bot",
        name="Test Bot",
        private_key="0"*64
    )
    session = BotSession(config_data)
    # Mock the bot
    session.bot = MagicMock()
    return session

@pytest.mark.asyncio
async def test_set_event_loop_stores_reference(mock_session):
    """Test that set_event_loop stores the loop reference."""
    loop = asyncio.get_running_loop()
    mock_session.set_event_loop(loop)
    assert mock_session._event_loop == loop

@pytest.mark.asyncio
async def test_callback_schedules_coroutine(mock_session):
    """Test that callback schedules the async handler on the event loop."""
    loop = asyncio.get_running_loop()
    mock_session.set_event_loop(loop)
    
    # Create an async mock handler
    async_handler = AsyncMock()
    mock_session.on_price_update = async_handler
    
    # Create a future to track when the async handler is actually executed
    handler_executed = asyncio.Future()
    
    async def wrapper(*args, **kwargs):
        # Determine if we are mocking the handler or if on_price_update IS the handler
        # In the implementation, on_price_update is called.
        # Here we mock it.
        await async_handler(*args, **kwargs)
        if not handler_executed.done():
            # Schedule setting result on the loop to be safe
            loop.call_soon_threadsafe(handler_executed.set_result, True)
            
    mock_session.on_price_update = wrapper
    
    # Run trigger in a separate thread to simulate Bot behavior
    def trigger_callback():
        # Call the method that uses run_coroutine_threadsafe
        mock_session._on_price_update({"price": 100})
        
    # Run trigger in a thread
    t = threading.Thread(target=trigger_callback)
    t.start()
    t.join()
    
    # Wait for the handler to be executed on the loop
    await asyncio.wait_for(handler_executed, timeout=1.0)
    
    # Verify handler was called
    assert handler_executed.result() is True
    assert async_handler.called


def test_session_has_event_loop_attribute_initially_none(mock_session):
    """BotSession should have _event_loop attribute initially None."""
    assert hasattr(mock_session, "_event_loop")
    assert mock_session._event_loop is None

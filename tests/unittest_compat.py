"""
Compatibility module for unittest.IsolatedAsyncioTestCase for older Python versions.
"""
from unittest import TestCase

try:
    from unittest import IsolatedAsyncioTestCase
except ImportError:
    # For Python < 3.8
    import asyncio
    class IsolatedAsyncioTestCase(TestCase):
        """Compatibility layer for Python versions that do not support IsolatedAsyncioTestCase."""
        def __init__(self, methodName="runTest"):
            super().__init__(methodName)
            self._asyncioTestLoop = None
        
        async def asyncSetUp(self):
            pass
        
        async def asyncTearDown(self):
            pass
        
        def run(self, result=None):
            self._setupAsyncioLoop()
            super().run(result)
            self._tearDownAsyncioLoop()
        
        def _setupAsyncioLoop(self):
            self._asyncioTestLoop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._asyncioTestLoop)
        
        def _tearDownAsyncioLoop(self):
            if self._asyncioTestLoop:
                self._asyncioTestLoop.close()
                asyncio.set_event_loop(None)
                self._asyncioTestLoop = None
        
        def _callAsync(self, coro):
            return self._asyncioTestLoop.run_until_complete(coro)
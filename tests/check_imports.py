print("1. Starting imports...")
try:
    import aiohttp
    print("2. aiohttp imported")
    from botbuilder.core import TurnContext
    print("3. botbuilder.core imported")
    from botbuilder.integration.aiohttp import CloudAdapter
    print("4. CloudAdapter imported")
except Exception as e:
    print(f"Import failed: {e}")
print("5. Done")

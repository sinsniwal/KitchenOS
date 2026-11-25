import asyncio
from agents.head_chef.agent import chef

async def main():
    tools = chef.tools if hasattr(chef, "tools") else []
    print([t.name if hasattr(t, "name") else t for t in tools])

asyncio.run(main())

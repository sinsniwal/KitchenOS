import asyncio
from google.adk.agents.llm_agent import Agent
from pydantic import BaseModel, Field

class DietInput(BaseModel):
    query: str = Field(..., description="Query")

class DietOutput(BaseModel):
    profiles: list[str] = Field(..., description="Profiles")

diet = Agent(
    model="openai/gpt-oss:120b-cloud",
    name="Diet",
    instruction="Return profiles.",
    input_schema=DietInput,
    output_schema=DietOutput,
)

chef = Agent(
    model="openai/gpt-oss:120b-cloud",
    name="Chef",
    instruction="Call Diet tool and return its output.",
    tools=[diet], # pass agent as tool
)

async def run():
    print(chef.model_fields.keys())
    print("Tools:", chef.tools)

asyncio.run(run())

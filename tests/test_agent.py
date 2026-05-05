"""
Test suite for agent structure and orchestration.

Verifies that all five agents (Diet, Recipe, Shopper, Budget) are
correctly instantiated with the expected relationships and toolsets under Chef.
"""
import pytest
from agents.head_chef.agent import (
    chef, diet, recipe, shopper, budget,
    spoonacular_toolset, postgres_toolset,
    swiggy_im_toolset, swiggy_food_toolset, swiggy_dineout_toolset
)


# ---------------------------------------------------------------------------
# Agent instantiation
# ---------------------------------------------------------------------------

def test_all_agents_instantiated():
    """All agents should be non-None."""
    assert chef is not None
    assert diet is not None
    assert recipe is not None
    assert shopper is not None
    assert budget is not None


def test_agent_names():
    """Each agent should have its expected name."""
    assert chef.name == "Chef"
    assert diet.name == "Diet"
    assert recipe.name == "Recipe"
    assert shopper.name == "Shopper"
    assert budget.name == "Budget"


def test_agent_descriptions_not_empty():
    """Each agent should have a non-empty description."""
    for agent in [chef, diet, recipe, shopper, budget]:
        assert agent.description, f"{agent.name} has empty description"


def test_agent_instructions_not_empty():
    """Each agent should have a non-empty instruction."""
    for agent in [chef, diet, recipe, shopper, budget]:
        assert agent.instruction, f"{agent.name} has empty instruction"


# ---------------------------------------------------------------------------
# Orchestration hierarchy
# ---------------------------------------------------------------------------

def test_chef_has_four_sub_agents():
    """Chef should orchestrate exactly four sub-agents."""
    assert len(chef.sub_agents) == 4


def test_chef_sub_agent_names():
    """Chef sub-agents should be Budget, Diet, Recipe, and Shopper."""
    names = sorted([a.name for a in chef.sub_agents])
    assert names == ["Budget", "Diet", "Recipe", "Shopper"]


def test_diet_parent_is_chef():
    """Diet's parent should be Chef."""
    assert diet.parent_agent is chef


def test_recipe_parent_is_chef():
    """Recipe's parent should be Chef."""
    assert recipe.parent_agent is chef


def test_shopper_parent_is_chef():
    """Shopper's parent should be Chef."""
    assert shopper.parent_agent is chef


def test_budget_parent_is_chef():
    """Budget's parent should be Chef."""
    assert budget.parent_agent is chef


def test_chef_has_no_parent():
    """Chef should be the root agent (no parent)."""
    assert chef.parent_agent is None


# ---------------------------------------------------------------------------
# Toolset assignments
# ---------------------------------------------------------------------------

def test_diet_has_toolsets():
    """Diet should have Postgres and Spoonacular MCP toolsets."""
    assert len(diet.tools) == 2
    assert postgres_toolset in diet.tools
    assert spoonacular_toolset in diet.tools


def test_recipe_has_toolsets():
    """Recipe should have Spoonacular and Postgres MCP toolsets."""
    assert len(recipe.tools) == 2
    assert spoonacular_toolset in recipe.tools
    assert postgres_toolset in recipe.tools


def test_shopper_has_toolsets():
    """Shopper should have Postgres and all 3 Swiggy MCP toolsets."""
    assert len(shopper.tools) == 4
    assert postgres_toolset in shopper.tools
    assert swiggy_im_toolset in shopper.tools
    assert swiggy_food_toolset in shopper.tools
    assert swiggy_dineout_toolset in shopper.tools


def test_chef_has_no_direct_tools():
    """Chef delegates to sub-agents, not direct tools."""
    assert len(chef.tools) == 0


def test_budget_has_no_tools():
    """Budget calculates strictly based on provided facts without external tools."""
    assert len(budget.tools) == 0


# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

def test_all_agents_share_same_model():
    """All agents should use the same model for consistency."""
    assert str(chef.model) == str(diet.model)
    assert str(chef.model) == str(recipe.model)
    assert str(chef.model) == str(shopper.model)
    assert str(chef.model) == str(budget.model)


def test_model_has_openai_prefix():
    """Model string must have openai/ prefix for litellm routing."""
    assert str(chef.model).startswith("openai/")


# ---------------------------------------------------------------------------
# Instruction Keyword Validation (Business Logic)
# ---------------------------------------------------------------------------

def test_diet_instruction():
    """Diet instruction should emphasize read-only operations and profiles."""
    instr = diet.instruction.upper()
    assert "READ-ONLY" in instr
    assert "NEVER" in instr


def test_shopper_handles_procurement():
    """Shopper instruction should mention procurement and Swiggy variants."""
    instr = shopper.instruction.lower()
    assert "swiggy" in instr
    assert "instamart" in instr
    assert "dineout" in instr


def test_chef_knows_family_workflow():
    """Chef instruction should mention gap analysis and constraints."""
    instr = chef.instruction.lower()
    assert "gap analysis" in instr
    assert "constraints" in instr


def test_recipe_accepts_constraints():
    """Recipe instruction should mention gap analysis and prioritizing expiring items."""
    instr = recipe.instruction.lower()
    assert "gap" in instr
    assert "expiring" in instr


def test_budget_instruction():
    """Budget instruction should emphasize arbitrage and savings calculations."""
    instr = budget.instruction.lower()
    assert "arbitrage" in instr
    assert "savings" in instr

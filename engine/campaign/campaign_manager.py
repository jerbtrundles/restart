# engine/campaign/campaign_manager.py
import os
import json
import random
import time
from typing import Dict, Optional, TYPE_CHECKING, Any
from engine.config import DATA_DIR
from engine.utils.logger import Logger
from .campaign_models import CampaignDefinition, CampaignNode

if TYPE_CHECKING:
    from engine.world.world import World
    from engine.player.core import Player

class CampaignManager:
    def __init__(self, world: 'World'):
        self.world = world
        self.definitions: Dict[str, CampaignDefinition] = {}
        self._load_definitions()

    def _load_definitions(self):
        path = os.path.join(DATA_DIR, "campaigns")
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            return

        for fname in os.listdir(path):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(path, fname), 'r') as f:
                        data = json.load(f)
                        defn = CampaignDefinition.from_dict(data)
                        self.definitions[defn.campaign_id] = defn
                except Exception as e:
                    Logger.error("CampaignManager", f"Failed to load {fname}: {e}")

    def start_campaign(self, campaign_id: str, player: 'Player') -> bool:
        if campaign_id not in self.definitions: return False
        
        # Check if already active or completed
        if campaign_id in player.active_campaigns or campaign_id in player.completed_campaigns:
            return False 
            
        definition = self.definitions[campaign_id]
        start_node = definition.nodes.get(definition.start_node_id)
        
        if not start_node: return False
        
        # Initialize State
        player.active_campaigns[campaign_id] = {
            "current_node": definition.start_node_id,
            "history": [],
            "variables": {}
        }
        
        Logger.info("CampaignManager", f"Started campaign '{definition.name}'")
        
        # Trigger the first node
        self._trigger_node(campaign_id, start_node, player)
        return True

    def handle_quest_completion(self, campaign_id: str, node_id: str, resolution: str, player: 'Player') -> str:
        """
        Called by QuestManager when a quest linked to a campaign node completes.
        Calculates the next node based on resolution.
        """
        definition = self.definitions.get(campaign_id)
        if not definition: return ""
        
        current_node = definition.nodes.get(node_id)
        if not current_node: return ""
        
        # Record History
        player_state = player.active_campaigns.get(campaign_id)
        if player_state:
            player_state["history"].append({"node_id": node_id, "resolution": resolution})
        
        # Find Next Node
        next_node_id = None
        transition_text = ""
        
        for transition in current_node.transitions:
            # 1. Check Trigger
            matches = False
            if transition.trigger == resolution:
                matches = True
            elif transition.trigger == "SUCCESS" and "SUCCESS" in resolution:
                matches = True
            elif transition.trigger == "FAILURE" and "FAILURE" in resolution:
                matches = True
                
            if matches:
                # 2. Check RNG (Twists)
                if transition.chance < 1.0 and random.random() > transition.chance:
                    continue 
                    
                next_node_id = transition.target_node_id
                transition_text = transition.narrative_text
                break
        
        if next_node_id:
            # Advance
            if player_state:
                player_state["current_node"] = next_node_id
                
            next_node = definition.nodes.get(next_node_id)
            if next_node:
                self._trigger_node(campaign_id, next_node, player)
                if transition_text:
                    return f"{transition_text}"
                return ""
        
        return "The campaign path ends here."

    def _trigger_node(self, campaign_id: str, node: CampaignNode, player: 'Player'):
        if node.node_type == "QUEST" and node.quest_template_id:
            # Context allows the quest to report back upon completion
            context = {"campaign_id": campaign_id, "node_id": node.node_id}
            
            # Start the Quest
            self.world.quest_manager.start_quest(node.quest_template_id, player, campaign_context=context)
            
        elif node.node_type == "END":
            Logger.info("CampaignManager", f"Campaign {campaign_id} ended: {node.outcome}")
            
            # Move to completed
            if campaign_id in player.active_campaigns:
                data = player.active_campaigns.pop(campaign_id)
                data["outcome"] = node.outcome
                data["end_time"] = time.time()
                player.completed_campaigns[campaign_id] = data
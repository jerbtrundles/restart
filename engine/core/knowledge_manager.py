# engine/core/knowledge_manager.py
import json
import os
import re
import uuid
from typing import Dict, Any, List, Set, Optional, Tuple, TYPE_CHECKING
from engine.config import DATA_DIR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_CATEGORY, FORMAT_ERROR

if TYPE_CHECKING:
    from engine.player import Player
    from engine.npcs.npc import NPC

class KnowledgeManager:
    def __init__(self, world):
        self.world = world
        self.topics: Dict[str, Any] = {}
        self.common_topics = ["job", "rumors"] 
        self._load_topics()

    def _load_topics(self):
        path = os.path.join(DATA_DIR, "knowledge", "topics.json")
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    self.topics = json.load(f)
            except Exception as e:
                print(f"Error loading topics: {e}")
                self.topics = {}
        else:
            print("Warning: topics.json not found.")

    def resolve_topic_id(self, input_text: str) -> Optional[str]:
        """
        Resolves user input (e.g., 'caravan', 'missing supplies') to a Topic ID (e.g., 'missing_supplies').
        """
        raw = input_text.lower().strip()
        
        # 1. Direct ID match
        if raw in self.topics: return raw
        
        # 2. Display Name & Keyword match
        for tid, data in self.topics.items():
            if data.get("display_name", "").lower() == raw: return tid
            for kw in data.get("keywords", []):
                if kw.lower() == raw: return tid
                
        # 3. Partial match (Startswith)
        for tid, data in self.topics.items():
            if data.get("display_name", "").lower().startswith(raw): return tid
            
        return None

    def get_response(self, npc: 'NPC', topic_id: str, player: 'Player') -> str:
        if "custom_dialog" in npc.properties and topic_id in npc.properties["custom_dialog"]:
            return npc.properties["custom_dialog"][topic_id]

        topic_data = self.topics.get(topic_id)
        if not topic_data:
            return f"\"{npc.name} looks confused. I don't know what that is.\""

        valid_responses = []
        for resp in topic_data.get("responses", []):
            conditions = resp.get("conditions", {})
            if self._check_conditions(npc, player, conditions):
                valid_responses.append(resp)

        if not valid_responses:
            return f"{npc.name} has nothing to say about {topic_data.get('display_name', topic_id)}."

        # Sort by priority
        valid_responses.sort(key=lambda x: x.get("priority", 0), reverse=True)
        chosen_response = valid_responses[0]
        
        # --- NEW: Process Effects ---
        self._process_response_effects(chosen_response, player)
        
        return f"\"{chosen_response['text']}\""

    def _check_conditions(self, npc, player, conditions: Dict) -> bool:
        for key, val in conditions.items():
            if key == "region_id" and npc.current_region_id != val: return False
            if key == "faction" and npc.faction != val: return False
            if key == "template_id" and npc.template_id != val: return False
            
            if key == "quest_state":
                req_state = val.get("state")
                from_this = val.get("from_this_npc", False)
                pattern = val.get("id_pattern")
                found_match = False
                
                logs_to_check = []
                if req_state == "active":
                    logs_to_check = [player.quest_log]
                elif req_state == "completed":
                    logs_to_check = [player.completed_quest_log, player.archived_quest_log]
                
                for log in logs_to_check:
                    for q_id, q_data in log.items():
                        if from_this and q_data.get("giver_instance_id") != npc.obj_id: continue
                        if pattern and pattern not in q_id: continue
                        if req_state == "active" and q_data.get("state") not in ["active", "ready_to_complete"]: continue
                        found_match = True; break
                    if found_match: break
                
                if not found_match: return False

        return True

    def parse_and_highlight(self, text: str, player: 'Player', source_npc: Optional['NPC'] = None) -> str:
        """
        Scans text for known topics and wraps them in clickable command tags.
        """
        if not text: return ""
        
        scannable = []
        for tid, data in self.topics.items():
            # Add Display Name
            scannable.append((data.get("display_name", tid), tid))
            # Add Keywords (aliases)
            for kw in data.get("keywords", []):
                scannable.append((kw, tid))
        
        # Sort by length descending to match longest phrases first (e.g., "missing supplies" before "supplies")
        scannable.sort(key=lambda x: len(x[0]), reverse=True)
        
        processed_text = text
        replacements = {}
        
        for phrase, topic_id in scannable:
            if len(phrase) < 3: continue 

            pattern_str = r"\b" + re.escape(phrase) + r"\b"
            pattern = re.compile(pattern_str, re.IGNORECASE)
            
            if pattern.search(processed_text):
                was_known = player.conversation.is_in_vocabulary(topic_id)
                
                if source_npc:
                    player.conversation.reveal_topic(source_npc.obj_id, topic_id)
                else:
                    player.conversation.learn_vocabulary(topic_id)
                
                color = FORMAT_HIGHLIGHT if was_known else FORMAT_CATEGORY
                
                def replace_func(match):
                    original_word = match.group(0)
                    token = f"__TOPIC_{uuid.uuid4().hex}__"
                    
                    # LOGIC CHANGE: Use the *original word* (or phrase) found in the text for the command.
                    # This ensures the output is "ask Merchant caravan" instead of "ask Merchant missing_supplies".
                    # The resolve_topic_id function will handle mapping "caravan" back to the ID later.
                    topic_arg = original_word
                    
                    cmd = f"ask {topic_arg}"
                    if source_npc:
                        cmd = f"ask {source_npc.name} {topic_arg}"
                        
                    final_tag = f"[[CMD:{cmd}]]{color}{original_word}{FORMAT_RESET}[[/CMD]]"
                    replacements[token] = final_tag
                    return token
                
                processed_text = pattern.sub(replace_func, processed_text)
        
        for token, tag in replacements.items():
            processed_text = processed_text.replace(token, tag)
                
        return processed_text

    def get_topics_for_npc(self, npc: 'NPC', player: 'Player') -> Tuple[List[str], List[str]]:
        unasked = []
        asked = []
        
        available_ids = set(self.common_topics)
        if npc.obj_id in player.conversation.npc_history:
            available_ids.update(player.conversation.npc_history[npc.obj_id]["revealed"])

        for topic_id in available_ids:
            if topic_id in self.topics:
                topic_data = self.topics[topic_id]
                has_valid_response = False
                for resp in topic_data.get("responses", []):
                    if self._check_conditions(npc, player, resp.get("conditions", {})):
                        has_valid_response = True
                        break
                
                if has_valid_response:
                    if player.conversation.has_discussed(npc.obj_id, topic_id):
                        asked.append(topic_id)
                    else:
                        unasked.append(topic_id)
        
        unasked.sort(key=lambda t: self.topics[t].get("display_name", t))
        asked.sort(key=lambda t: self.topics[t].get("display_name", t))
        
        return unasked, asked

    def _process_response_effects(self, response_data: Dict, player: 'Player'):
            """Handles side effects defined in topics.json responses."""
            effects = response_data.get("effects", {})
            
            # 1. Start Quest
            if "start_quest" in effects:
                quest_id = effects["start_quest"]
                self.world.quest_manager.start_quest(quest_id, player)
                
            # 2. Start Campaign (NEW)
            if "start_campaign" in effects:
                campaign_id = effects["start_campaign"]
                self.world.quest_manager.start_campaign(campaign_id, player)
                
            # 3. Give Item (Optional Utility)
            if "give_item" in effects:
                item_id = effects["give_item"]
                item = self.world.item_factory.create_item_from_template(item_id, self.world)
                if item: player.inventory.add_item(item)

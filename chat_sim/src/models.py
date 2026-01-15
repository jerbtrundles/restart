from dataclasses import dataclass, asdict
import time

@dataclass
class Character:
    name: str
    prompt: str

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data):
        return Character(name=data['name'], prompt=data['prompt'])

@dataclass
class ChatMessage:
    sender: str
    text: str
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
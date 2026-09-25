"""
Life Story Interviewer Harness

Loads a 7B model with the interviewer persona, manages the conversation loop,
and tracks which life phase the interview is in.

Usage:
    from interviewer_harness import Interviewer
    iv = Interviewer(model_id="mlx-community/Qwen2.5-7B-Instruct-4bit")
    response = iv.start()
    response = iv.respond("I grew up in a small town...")
    response = iv.respond("...")

The harness:
- Loads the model once and keeps it warm
- Injects the persona file as system prompt
- Tracks the current life phase (Roots -> Legacy)
- Can nudge the model toward a new phase
- Logs the full conversation
"""

import json
import time
from pathlib import Path
from datetime import datetime

from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

# ── Phases ──────────────────────────────────────────────────────────────

PHASES = [
    "Roots",
    "Becoming",
    "Love",
    "Work",
    "Loss",
    "Joy",
    "Wisdom",
    "Legacy",
]

PHASE_PROMPTS = {
    "Roots": "The interview is in the Roots phase — childhood, family, where they came from.",
    "Becoming": "The interview is in the Becoming phase — who they were becoming, formative years.",
    "Love": "The interview is in the Love phase — partnership, family, the people who mattered.",
    "Work": "The interview is in the Work phase — what they did, what it meant, what it cost.",
    "Loss": "The interview is in the Loss phase — hard things, survival, what they carry.",
    "Joy": "The interview is in the Joy phase — moments of aliveness, pride, the good stuff.",
    "Wisdom": "The interview is in the Wisdom phase — what they know now that they didn't then.",
    "Legacy": "The interview is in the Legacy phase — what they want to leave behind.",
}


# ── Interviewer ────────────────────────────────────────────────────────

class Interviewer:
    def __init__(
        self,
        model_id="mlx-community/Qwen2.5-7B-Instruct-4bit",
        persona_path=None,
        log_dir=None,
    ):
        self.model_id = model_id
        self.persona_path = persona_path or Path(__file__).parent / "interviewer-soul.md"
        self.log_dir = Path(log_dir) if log_dir else Path(__file__).parent / "interviews"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.current_phase = "Roots"
        self.turn_count = 0
        self.messages = []
        self.log_entries = []

        # Topic tracking — prevents getting stuck on one subject
        self.current_topic = None
        self.topic_turns = 0
        self.max_topic_turns = 2  # After 2 turns on same topic, nudge

        # Load model
        print(f"Loading {model_id}...")
        self.model, self.tokenizer = load(model_id)
        self.sampler = make_sampler(temp=0.65, top_p=0.9, top_k=50)
        print("Model ready.")

        # Build system prompt
        self._set_phase("Roots")

    def _set_phase(self, phase):
        """Set the current life phase and build the system prompt."""
        self.current_phase = phase
        persona = Path(self.persona_path).read_text()
        system_content = f"{persona}\n\n## Current Phase\n{PHASE_PROMPTS[phase]}"
        # Replace existing system prompt
        self.messages = [
            {"role": "system", "content": system_content}
        ]

    def _bridge_to(self, phase):
        """Transition to a new phase with a bridging message."""
        if phase == self.current_phase:
            return None
        old_phase = self.current_phase
        self._set_phase(phase)
        self._log("phase_change", {"from": old_phase, "to": phase})
        return f"[Bridging from {old_phase} to {phase}]"

    def start(self):
        """Begin the interview. Returns the opening message."""
        return self.respond("__START__")

    def _detect_topic(self, text):
        """Simple keyword-based topic detection."""
        text_lower = text.lower()
        topics = {
            "fog": ["fog", "mist", "haze"],
            "ocean": ["ocean", "sea", "wave", "beach", "coast", "pacific"],
            "family": ["family", "mother", "father", "parent", "sister", "brother", "mom", "dad", "grandma", "grandpa"],
            "work": ["work", "job", "career", "office", "company", "boss", "coworker"],
            "school": ["school", "teacher", "class", "student", "college", "university"],
            "love": ["love", "wife", "husband", "partner", "girlfriend", "boyfriend", "marriage", "divorce"],
            "loss": ["loss", "died", "death", "funeral", "grief", "passed away"],
            "joy": ["joy", "happy", "laugh", "fun", "celebrate", "proud", "best moment"],
            "fear": ["fear", "afraid", "scared", "anxiety", "worry", "nightmare"],
            "childhood": ["childhood", "kid", "young", "grew up", "playing", "game", "toy"],
        }
        for topic, keywords in topics.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        return None

    def _maybe_nudge_topic(self):
        """If stuck on same topic, return a nudge message to inject."""
        if self.topic_turns < self.max_topic_turns:
            return None

        # Build a nudge asking to move on — more explicit
        import random
        topic_prompts = {
            "ocean": "family or your childhood home",
            "fog": "family or your childhood home",
            "family": "work or school",
            "work": "family or love",
            "school": "family or work",
            "love": "family or work",
            "loss": "joy or something you're proud of",
            "joy": "work or school",
            "fear": "joy or something that made you laugh",
            "childhood": "work or love",
        }
        next_topic = topic_prompts.get(self.current_topic, "something else")
        return f"We've been talking about {self.current_topic} for a bit. Let me ask you about {next_topic} instead. "

    def respond(self, user_input):
        """
        Process user input and return the interviewer's next question.

        If user_input is "__START__", generates the opening.
        """
        if user_input == "__START__":
            user_input = "Hi, I'm ready to start."

        # Add user message
        self.messages.append({"role": "user", "content": user_input})
        self.turn_count += 1

        # Track topic
        detected = self._detect_topic(user_input)
        if detected == self.current_topic:
            self.topic_turns += 1
        else:
            self.current_topic = detected
            self.topic_turns = 1

        # Maybe nudge if stuck
        nudge = self._maybe_nudge_topic()
        if nudge:
            # Inject nudge as a user message so the model sees it clearly
            self.messages.append({"role": "user", "content": nudge})

        # Generate response
        prompt = self.tokenizer.apply_chat_template(
            self.messages, tokenize=False, add_generation_prompt=True
        )
        start_time = time.time()
        result = generate(
            self.model, self.tokenizer,
            prompt=prompt, max_tokens=512,
            sampler=self.sampler,
        )
        elapsed = time.time() - start_time

        # Remove nudge from conversation history if it was added
        if nudge and self.messages[-1]["role"] == "user" and self.messages[-1]["content"] == nudge:
            self.messages.pop()

        # Add assistant message
        self.messages.append({"role": "assistant", "content": result})

        # Log
        self._log("turn", {
            "turn": self.turn_count,
            "user": user_input[:100],
            "assistant": result[:200],
            "tokens": len(self.tokenizer.encode(result)),
            "time_seconds": round(elapsed, 2),
            "topic": detected,
            "nudged": bool(nudge),
        })

        return result

    def nudge_phase(self, phase):
        """
        Suggest moving to a new phase. The harness will bridge
        if the model isn't already there.
        """
        if phase not in PHASES:
            raise ValueError(f"Unknown phase: {phase}. Choose from: {PHASES}")
        return self._bridge_to(phase)

    def get_conversation(self):
        """Return the full conversation as a list of messages."""
        return self.messages.copy()

    def save_transcript(self, filename=None):
        """Save the conversation to a JSON file."""
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"interview_{ts}.json"

        path = self.log_dir / filename
        data = {
            "model": self.model_id,
            "persona": str(self.persona_path),
            "phase": self.current_phase,
            "turns": self.turn_count,
            "timestamp": datetime.now().isoformat(),
            "messages": self.messages,
        }
        path.write_text(json.dumps(data, indent=2))
        print(f"Transcript saved: {path}")
        return path

    def _log(self, event_type, data):
        """Append to the internal log."""
        self.log_entries.append({
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **data,
        })

    def __repr__(self):
        return (
            f"<Interviewer phase={self.current_phase} "
            f"turns={self.turn_count} "
            f"model={self.model_id}>"
        )


# ── CLI Demo ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("  Life Story Interviewer — Demo")
    print("=" * 60)
    print()

    iv = Interviewer()
    print()
    print(f"  {iv}")
    print()

    # Opening
    opening = iv.start()
    print(f"[Interviewer] {opening}")
    print()

    # Simulate a few turns
    test_inputs = [
        "I grew up in a small town in Oregon. My dad worked at the lumber mill. I remember the smell of sawdust everywhere.",
        "He was a quiet man. Didn't talk much. But he showed up every day. That meant something to me.",
        "I had a dog named Rusty — he was my best friend. One day he ran away and I never saw him again. I was devastated.",
        "Rusty was a mutt, brown and white. He followed me everywhere. When he ran away, I blamed myself for not closing the gate.",
    ]

    for user_input in test_inputs:
        print(f"[You] {user_input}")
        print()
        response = iv.respond(user_input)
        print(f"[Interviewer] {response}")
        print()

    # Save transcript
    iv.save_transcript("demo_interview.json")
    print()
    print("Done.")

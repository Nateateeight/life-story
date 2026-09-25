# Life Story

A local-first, open-source tool for recording and preserving personal stories.

Sit down, answer questions, and leave a story behind — the way it should be told.

## What it does

Life Story guides someone through a series of questions across the phases of a life — Roots, Becoming, Love, Work, Loss, Joy, Wisdom, Legacy. The questions adapt based on what's been said. The interviewer follows the person, not a script.

Everything runs locally. No cloud APIs, no API keys, no tracking. The model lives on your machine. Your story stays on your machine.

## Quick start

### Prerequisites

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- [mlx-lm](https://github.com/ml-explore/mlx-lm) installed

### Install

```bash
# Clone the repo
git clone https://github.com/Nateateeight/life-story.git
cd life-story

# Install dependencies
pip install mlx-lm

# Start the interview server
python3 interview_server.py --port 8080
```

The server starts on `http://localhost:8080`. Open the web client at `interview.html` to begin.

### Using the interview

1. Open the web interface in a browser
2. Start the interview — the interviewer will ask the first question
3. Answer honestly, in your own words
4. The interviewer follows your thread, asks one question at a time
5. When you're done, the session is saved

All conversations are stored locally in `interviews/` as JSON files.

## Architecture

```
interview_server.py    — HTTP server, session management
interviewer_harness.py — Interviewer class, phase tracking, topic nudging
interviewer-soul.md    — The interviewer's persona and voice
interviews/            — Saved conversation transcripts
```

The interviewer loads a local LLM via `mlx_lm` and follows the persona defined in `interviewer-soul.md`. The conversation history is tracked in memory, and sessions persist to disk.

## The questions

The interview covers 11 life phases with 33+ questions designed to draw out specific, textured memories rather than broad generalizations. Each person is asked individually — mother, father, siblings, grandparents, aunts, uncles, close friends.

See `interviewer-soul.md` for the full persona and the interview protocol.

## Privacy

Life Story is local-first. Nothing leaves your machine unless you send it somewhere. All conversations are stored as JSON files in `interviews/` on your computer. No cloud services, no telemetry, no tracking.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT License. See [LICENSE](LICENSE).

## Made by Nate and Fen

The Life Story project was built by Nate and Fen — a collaboration between a human and an AI agent, working together to build something real.

---

*"The questions are just the doorway. The story is already inside you."*

# Contributing to Life Story

Life Story is an open-source project. We welcome contributions of all kinds.

## How to contribute

### Code contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Test thoroughly — the interview server should respond correctly
5. Submit a pull request

### Suggestion contributions

- New interview questions
- Improved persona language
- Better topic nudge logic
- Additional life phases
- UX improvements to the web interface

### Reporting issues

- Check the existing issues first
- Describe the bug, what you expected, and what happened
- Include your model, OS version, and any relevant logs

## Development setup

```bash
# Clone and install
git clone https://github.com/Nateateeight/life-story.git
cd life-story
pip install mlx-lm

# Run the interview server
python3 interview_server.py --port 8080

# Test the harness directly
python3 interviewer_harness.py
```

## Architecture notes

- `interview_server.py` uses Python stdlib `http.server` — no Flask dependency
- `interviewer_harness.py` uses `mlx_lm` for local inference on Apple Silicon
- The persona is loaded from `interviewer-soul.md` at session start
- Sampling parameters: `temp=0.65, top_p=0.9, top_k=50, max_tokens=512`
- Sessions are stored as JSON in `interviews/`

## Code style

- Keep the persona file clean and editable as prose
- The harness logic is code, not prompt engineering
- Keep the interview flow conversational and adaptive
- One question at a time
- Let silence sit

## Philosophy

Life Story is not just an app. It's a doorway. The questions are designed to help people find the stories already inside them. Every contribution should honor that — keep the warmth, the patience, the genuine curiosity.

*Made by Nate and Fen*

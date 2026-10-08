"""What kind of turn is this? Sight (about the camera image now), recall (about earlier
observations), social (small talk, greetings, things about the visitor), or knowledge (Qdrant
and the robot). A nearest-neighbour vote over example lines, on the bge vector the turn already
has; each kind gets only the evidence it needs (counsel reviews/20261008-072616-91017-design.md).
"""
import numpy as np

K = 5
EXAMPLES = {
    "sight": [
        "What do you see?", "What is this?", "What am I holding?", "What color is the car?",
        "How many people are there?", "Can you read the sign?", "What is on the table?",
        "What's on your right?", "Describe the room.", "Is the light on?",
        "What is the man doing?", "What brand is this laptop?", "Is it still there?",
        "What animal is that?", "Look at this.", "Do you like my shirt?",
        "What can you see now?", "And now?", "What's in front of you?",
    ],
    "recall": [
        "What did I show you?", "What was on your left earlier?", "What did you see before?",
        "What was the last thing you saw?", "Did you see my keys?", "What did we talk about?",
        "Have you seen this before?", "What was I wearing?", "Where did I put my phone?",
        "What happened while I was away?", "Which object came second?",
        "What did I bring yesterday?",
    ],
    "social": [
        "Hi there!", "Good afternoon.", "How are you?", "My name is Sam.",
        "I'm from Lisbon.", "Nice to meet you.", "Tell me a joke.", "What's my name?",
        "Can you tell me something funny?", "Do you know any riddles?", "Sing me a song.",
        "Where am I from?", "I love pizza.", "Thanks, bye!", "What do I like to drink?",
        "I work at a hospital.", "Who are you?", "What's your favorite color?",
        "What's the capital of Japan?",
    ],
    "knowledge": [
        "What is Qdrant?", "How does vector search work?", "What is Qdrant Edge?",
        "Does it need a server?", "Is Qdrant open source?", "What is a multivector?",
        "How fast is your memory?", "What hardware do you run on?", "How do you remember things?",
        "Can I use it from Rust?", "What is hybrid search?", "Where is your data stored?",
    ],
}


class Router:
    def __init__(self, embed):
        self.labels = [kind for kind, lines in EXAMPLES.items() for _ in lines]
        self.vectors = embed([line for lines in EXAMPLES.values() for line in lines])

    def __call__(self, question: np.ndarray) -> str:
        """The kind of a unit-length bge question vector: a vote of the K nearest examples."""
        nearest = np.argsort(self.vectors @ question)[-K:]
        kinds = [self.labels[i] for i in nearest]
        return max(EXAMPLES, key=lambda kind: (kinds.count(kind), kind == "sight"))


if __name__ == "__main__":
    from robot.text_embed import TextEmbedder
    embed = TextEmbedder()
    route = Router(embed)
    cases = {"What's on the plate?": "sight", "What did I just have in my hand?": "recall",
             "Hello robot, I'm Ana.": "social", "Tell me what Qdrant Edge is.": "knowledge",
             "Do you remember where I'm from?": "social", "What's in front of you?": "sight"}
    got = {q: route(v) for q, v in zip(cases, embed(list(cases)), strict=True)}
    wrong = {q: (got[q], want) for q, want in cases.items() if got[q] != want}
    assert not wrong, wrong
    print("selftest ok")

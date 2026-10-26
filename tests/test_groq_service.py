import json
import unittest
from types import SimpleNamespace

from lecturelens.groq_service import (
    GroqConfigurationError,
    GroqGenerationError,
    GroqLectureGenerator,
)


SOURCE = (
    "Neural networks learn patterns by adjusting weights during training. "
    "ReLU keeps positive signals and changes negative signals to zero. "
    "Sigmoid maps values into a range between zero and one. "
    "Backpropagation updates weights using output error."
)


class FakeCompletions:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = iter(payloads)

    def create(self, **kwargs: object) -> object:
        payload = next(self.payloads)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(payload))
                )
            ]
        )


class FakeClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.models = SimpleNamespace(
            list=lambda: SimpleNamespace(data=[SimpleNamespace(id="test-model")])
        )
        self.chat = SimpleNamespace(completions=FakeCompletions(payloads))


def analysis_payload() -> dict:
    return {
        "short_summary": "Neural networks learn patterns from data.",
        "detailed_summary": "The lecture explains activation functions and training.",
        "headings": ["Neural network training"],
        "important_concepts": ["neural networks", "activation functions"],
        "bullet_points": ["Weights change during training."],
        "supported_definitions": [],
        "examples": [],
        "key_takeaways": ["Training changes weights using error."],
        "keywords": [{"phrase": "neural networks", "score": 1.0}],
        "glossary": [],
    }


class GroqServiceTests(unittest.TestCase):
    def test_analysis_maps_structured_response(self) -> None:
        generator = GroqLectureGenerator(
            client=FakeClient([analysis_payload()]),
            api_key="test-key",
            model="test-model",
        )

        result = generator.generate_analysis(SOURCE)

        self.assertEqual(result.summaries.short, "Neural networks learn patterns from data.")
        self.assertEqual(result.notes.important_concepts, ("neural networks", "activation functions"))
        self.assertEqual(result.keywords[0].phrase, "neural networks")

    def test_malformed_response_is_rejected(self) -> None:
        class MalformedClient(FakeClient):
            def __init__(self) -> None:
                self.models = SimpleNamespace(
                    list=lambda: SimpleNamespace(data=[SimpleNamespace(id="test-model")])
                )
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(
                        create=lambda **kwargs: SimpleNamespace(
                            choices=[SimpleNamespace(message=SimpleNamespace(content="{bad json"))]
                        )
                    )
                )

        generator = GroqLectureGenerator(
            client=MalformedClient(), api_key="test-key", model="test-model"
        )

        with self.assertRaisesRegex(GroqGenerationError, "malformed JSON"):
            generator.generate_analysis(SOURCE)

    def test_empty_source_is_rejected(self) -> None:
        generator = GroqLectureGenerator(api_key="test-key", model="test-model")

        with self.assertRaisesRegex(GroqGenerationError, "empty or too short"):
            generator.generate_analysis(" ")

    def test_unavailable_model_is_rejected(self) -> None:
        client = FakeClient([analysis_payload()])
        client.models = SimpleNamespace(
            list=lambda: SimpleNamespace(data=[SimpleNamespace(id="other-model")])
        )
        generator = GroqLectureGenerator(
            client=client, api_key="test-key", model="test-model"
        )

        with self.assertRaisesRegex(GroqConfigurationError, "not available"):
            generator.generate_analysis(SOURCE)

    def test_quiz_keeps_only_valid_source_supported_questions(self) -> None:
        payload = {
            "questions": [
                {
                    "question": "What does ReLU do?",
                    "options": [
                        "Keeps positive signals",
                        "Stores video captions",
                        "Deletes all weights",
                        "Measures page count",
                    ],
                    "correct_index": 0,
                    "explanation": "The lecture states that ReLU keeps positive signals.",
                    "source_passage": "ReLU keeps positive signals and changes negative signals to zero.",
                },
                {
                    "question": "Invalid duplicate options",
                    "options": ["same", "same", "other", "third"],
                    "correct_index": 0,
                    "explanation": "Invalid.",
                    "source_passage": SOURCE,
                },
            ]
        }
        generator = GroqLectureGenerator(
            client=FakeClient([payload]), api_key="test-key", model="test-model"
        )

        result = generator.generate_quiz(SOURCE, 5)

        self.assertEqual(len(result.questions), 1)
        self.assertEqual(len(result.questions[0].options), 4)

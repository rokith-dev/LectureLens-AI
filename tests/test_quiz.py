import unittest

from lecturelens.quiz import QuizGenerationError, generate_quiz
from lecturelens.study_materials import extract_keywords, generate_glossary


TEXT = (
    "Spaced repetition is a learning method that schedules reviews over time. "
    "Retrieval practice means recalling information without looking at notes. "
    "Metacognition is the process of thinking about one's own learning. "
    "Cognitive load is the amount of mental effort used by working memory. "
    "For example, students can use practice questions after each lecture."
)


class QuizTests(unittest.TestCase):
    def setUp(self) -> None:
        self.keywords = extract_keywords(TEXT)
        self.glossary = generate_glossary(TEXT, self.keywords)

    def test_generates_valid_four_option_questions(self) -> None:
        result = generate_quiz(TEXT, 5, self.glossary, self.keywords)

        self.assertGreaterEqual(len(result.questions), 1)
        for question in result.questions:
            self.assertEqual(len(question.options), 4)
            self.assertEqual(len(set(question.options)), 4)
            self.assertIn(question.correct_index, range(4))
            self.assertIn(question.source_passage, TEXT)

    def test_detects_duplicate_questions(self) -> None:
        result = generate_quiz(TEXT, 15, self.glossary, self.keywords)
        question_texts = [question.question for question in result.questions]

        self.assertEqual(len(question_texts), len(set(question_texts)))

    def test_rejects_empty_and_invalid_input(self) -> None:
        with self.assertRaises(QuizGenerationError):
            generate_quiz("", 5)
        with self.assertRaises(QuizGenerationError):
            generate_quiz(TEXT, 7, self.glossary, self.keywords)

    def test_rejects_short_lectures_without_four_supported_concepts(self) -> None:
        short_text = "Spaced repetition is a learning method."
        glossary = generate_glossary(short_text, extract_keywords(short_text))

        with self.assertRaisesRegex(QuizGenerationError, "four distinct"):
            generate_quiz(short_text, 5, glossary)

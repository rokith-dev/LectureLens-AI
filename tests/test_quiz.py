import unittest

from lecturelens.quiz import (
    QuizGenerationError,
    QuizQuestion,
    QuizResult,
    generate_quiz,
    revision_recommendations,
    score_quiz,
)
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

    def test_scores_all_correct_all_incorrect_and_unanswered(self) -> None:
        quiz = generate_quiz(TEXT, 5, self.glossary, self.keywords)
        all_correct = {index: question.correct_index for index, question in enumerate(quiz.questions)}
        all_incorrect = {index: (question.correct_index + 1) % 4 for index, question in enumerate(quiz.questions)}
        unanswered = {index: None for index in range(len(quiz.questions))}

        self.assertEqual(score_quiz(quiz, all_correct).percentage, 100.0)
        self.assertEqual(score_quiz(quiz, all_incorrect).correct_count, 0)
        self.assertEqual(score_quiz(quiz, unanswered).answered_count, 0)
        self.assertEqual(score_quiz(quiz, unanswered).percentage, 0.0)

    def test_zero_valid_questions_do_not_divide(self) -> None:
        malformed = QuizResult(
            requested_count=5,
            questions=(
                QuizQuestion("Bad", ("only", "two"), 0, "why", "source"),
            ),
        )

        result = score_quiz(malformed, {0: 0})

        self.assertEqual(result.valid_question_count, 0)
        self.assertEqual(result.percentage, 0.0)

    def test_scoring_is_idempotent_for_duplicate_submission(self) -> None:
        quiz = generate_quiz(TEXT, 5, self.glossary, self.keywords)
        answers = {index: question.correct_index for index, question in enumerate(quiz.questions)}

        first = score_quiz(quiz, answers)
        second = score_quiz(quiz, answers)

        self.assertEqual(first, second)

    def test_revision_recommendations_include_only_incorrect_answers(self) -> None:
        quiz = generate_quiz(TEXT, 5, self.glossary, self.keywords)
        answers = {index: question.correct_index for index, question in enumerate(quiz.questions)}
        answers[0] = (quiz.questions[0].correct_index + 1) % 4

        recommendations = revision_recommendations(quiz, answers)

        self.assertEqual(len(recommendations), 1)
        self.assertIn(quiz.questions[0].source_passage, recommendations[0].source_passage)

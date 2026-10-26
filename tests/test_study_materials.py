import unittest

from lecturelens.study_materials import (
    StudyMaterialsError,
    extract_keywords,
    generate_glossary,
    generate_study_notes,
    normalize_lecture_text,
)


LECTURE = (
    "Spaced repetition is a learning method that schedules reviews over time. "
    "Retrieval practice means recalling information without looking at notes. "
    "For example, students can use practice questions after each lecture. "
    "These methods improve retention and make study sessions more effective."
)


class StudyMaterialsTests(unittest.TestCase):
    def test_keywords_are_ranked_and_deduplicated(self) -> None:
        keywords = extract_keywords(LECTURE)

        self.assertTrue(keywords)
        self.assertEqual(len({keyword.phrase for keyword in keywords}), len(keywords))
        self.assertTrue(all(keyword.score > 0 for keyword in keywords))

    def test_keywords_handle_short_and_empty_text(self) -> None:
        self.assertTrue(extract_keywords("Memory"))
        with self.assertRaises(StudyMaterialsError):
            extract_keywords(" ")

    def test_glossary_flags_context_without_explicit_definition(self) -> None:
        glossary = generate_glossary(LECTURE)

        spaced = next(entry for entry in glossary if entry.term == "spaced repetition")
        self.assertFalse(spaced.needs_verification)
        self.assertTrue(any(entry.needs_verification for entry in glossary))

    def test_study_notes_use_summary_and_source_sentences(self) -> None:
        notes = generate_study_notes(
            LECTURE,
            "Spaced repetition and retrieval practice improve learning.",
            "The lecture explains two review methods and gives practice-question examples.",
        )

        self.assertIn("two review methods", notes.overview)
        self.assertTrue(notes.headings)
        self.assertTrue(notes.bullet_points)
        self.assertTrue(notes.examples)
        self.assertTrue(notes.supported_definitions)

    def test_study_notes_reject_missing_summary_context(self) -> None:
        with self.assertRaises(StudyMaterialsError):
            generate_study_notes(LECTURE, "", "Detailed summary")

    def test_normalization_removes_artifacts_without_losing_multilingual_text(self) -> None:
        noisy = (
            "ReLU &amp; sigmoid are activation functions.\n"
            "ReLU &amp; sigmoid are activation functions.\n"
            "sigmoid sigmoid sigmoid\n"
            "الشبكات العصبية تتعلم من البيانات."
        )

        normalized = normalize_lecture_text(noisy)

        self.assertEqual(normalized.count("activation functions"), 1)
        self.assertNotIn("sigmoid sigmoid sigmoid", normalized)
        self.assertIn("الشبكات العصبية", normalized)

    def test_notes_deduplicate_repeated_source_sentences(self) -> None:
        text = (
            "Neural networks learn patterns from data. "
            "Neural networks learn patterns from data. "
            "ReLU is an activation function."
        )
        notes = generate_study_notes(text, "Neural networks learn from data.", "A lecture about neural networks.")

        self.assertEqual(len(notes.bullet_points), 2)
        self.assertEqual(len(notes.key_takeaways), len(set(notes.key_takeaways)))

import streamlit as st

from lecturelens.models import LectureText
from lecturelens.pdf_input import PdfInputError, extract_pdf_text
from lecturelens.quiz import revision_recommendations, score_quiz
from lecturelens.groq_service import (
    GroqConfigurationError,
    GroqGenerationError,
    GroqLectureGenerator,
)
from lecturelens.youtube_input import (
    YouTubeInputError,
    create_manual_youtube_lecture,
    fetch_youtube_transcript,
)


@st.cache_resource
def get_groq_generator() -> GroqLectureGenerator:
    return GroqLectureGenerator()


def _render_header() -> None:
    st.set_page_config(page_title="LectureLens AI", page_icon="📚", layout="wide")
    st.title("LectureLens AI")
    st.caption("Turn a lecture PDF or YouTube transcript into focused study materials.")


def _render_input() -> LectureText | None:
    with st.sidebar:
        st.header("Lecture source")
        source = st.radio(
            "Choose one input method",
            ("PDF upload", "YouTube URL"),
            help="LectureLens supports PDF files and accessible YouTube captions only.",
        )

        if source == "PDF upload":
            uploaded_file = st.file_uploader(
                "Upload a lecture PDF",
                type=["pdf"],
                help="Scanned or image-only PDFs require OCR, which is not included.",
            )
            if uploaded_file is None:
                st.info("Upload a PDF to begin.")
                return None
            with st.spinner("Extracting text from the PDF..."):
                try:
                    return extract_pdf_text(uploaded_file.getvalue(), uploaded_file.name)
                except PdfInputError as error:
                    st.error(str(error))
                    return None

        youtube_url = st.text_input(
            "YouTube video URL",
            placeholder="https://www.youtube.com/watch?v=...",
            help="The video must provide accessible captions or a transcript.",
        )
        if youtube_url.strip():
            with st.spinner("Retrieving available captions..."):
                try:
                    return fetch_youtube_transcript(youtube_url)
                except YouTubeInputError as error:
                    st.error(str(error))
        else:
            st.info("Enter a YouTube URL or paste its transcript below.")

        st.subheader("Paste YouTube Transcript")
        st.caption(
            "Use this fallback when YouTube blocks caption requests or no accessible "
            "transcript is available."
        )
        pasted_text = st.text_area(
            "YouTube captions/transcript",
            height=240,
            placeholder="Paste the video's captions or transcript here.",
            key="manual_youtube_transcript",
        )
        if st.button("Process pasted transcript", key="process_manual_youtube"):
            try:
                return create_manual_youtube_lecture(pasted_text, youtube_url)
            except YouTubeInputError as error:
                st.error(str(error))
        return None


def _render_lecture_metadata(lecture: LectureText) -> None:
    st.success("Lecture text is ready.")
    st.subheader(lecture.title)
    metadata = " · ".join(
        f"{key.replace('_', ' ').title()}: {value}"
        for key, value in lecture.metadata.items()
    )
    st.caption(metadata)
    with st.expander("Preview extracted lecture text"):
        st.text_area("Lecture text", lecture.text, height=220, label_visibility="collapsed")


def _generate_analysis(lecture: LectureText) -> None:
    if not lecture.text.strip():
        st.error("No readable lecture text was extracted. Nothing can be generated.")
        return

    with st.spinner("Generating summaries and study materials..."):
        try:
            generated = get_groq_generator().generate_analysis(lecture.text)
            summaries = generated.summaries
            keywords = generated.keywords
            glossary = generated.glossary
            notes = generated.notes
        except (GroqConfigurationError, GroqGenerationError) as error:
            st.error(str(error))
            return

    analysis = {
        "source_text": lecture.text,
        "summaries": summaries,
        "keywords": keywords,
        "glossary": glossary,
        "notes": notes,
    }
    if not summaries.short.strip() or not summaries.detailed.strip() or not notes.overview.strip():
        st.error("Generation returned incomplete results. Please try again.")
        return
    st.session_state["analysis"] = analysis
    for key in ("quiz", "quiz_error", "quiz_answers", "quiz_score", "quiz_recommendations"):
        st.session_state.pop(key, None)
    st.success("Summaries and study materials generated.")


def _render_summary(analysis: dict) -> None:
    summaries = analysis["summaries"]
    st.subheader("Summary")
    st.write("**Short summary**")
    st.info(summaries.short)
    st.write("**Detailed summary**")
    st.write(summaries.detailed)
    st.caption(f"Processed {summaries.chunk_count} lecture text chunk(s).")


def _render_study_materials(analysis: dict) -> None:
    notes = analysis["notes"]
    st.subheader("Study notes")
    st.write("**Overview**")
    st.write(notes.overview)

    left, right = st.columns(2)
    with left:
        st.write("**Main headings**")
        for heading in notes.headings:
            st.markdown(f"- {heading}")
        st.write("**Important concepts**")
        for concept in notes.important_concepts:
            st.markdown(f"- {concept}")
    with right:
        st.write("**Key takeaways**")
        for takeaway in notes.key_takeaways:
            st.markdown(f"- {takeaway}")
        if notes.examples:
            st.write("**Examples from the lecture**")
            for example in notes.examples:
                st.markdown(f"- {example}")

    st.write("**Lecture notes**")
    for bullet in notes.bullet_points:
        st.markdown(f"- {bullet}")

    glossary = analysis["glossary"]
    if glossary:
        st.subheader("Glossary")
        for entry in glossary:
            marker = " — needs verification" if entry.needs_verification else ""
            st.markdown(f"- **{entry.term}:** {entry.definition}{marker}")

    st.subheader("Keywords")
    keywords = analysis["keywords"]
    if keywords:
        st.write(" · ".join(keyword.phrase for keyword in keywords))
    else:
        st.info("No meaningful keywords were found.")


def _render_quiz(lecture: LectureText, analysis: dict) -> None:
    st.subheader("Interactive quiz")
    st.caption("Choose one answer per question. Unanswered questions count as incorrect.")

    quiz = st.session_state.get("quiz")
    if quiz is None:
        question_count = st.selectbox(
            "Number of questions",
            options=(5, 10, 15),
            key="quiz_question_count",
        )
        if st.button("Generate quiz", type="primary"):
            with st.spinner("Generating validated quiz questions..."):
                try:
                    st.session_state["quiz"] = get_groq_generator().generate_quiz(
                        lecture.text, question_count
                    )
                    st.session_state.pop("quiz_error", None)
                    st.rerun()
                except (GroqConfigurationError, GroqGenerationError) as error:
                    st.session_state["quiz_error"] = str(error)
        if st.session_state.get("quiz_error"):
            st.warning(st.session_state["quiz_error"])
        return

    for index, question in enumerate(quiz.questions):
        if len(question.options) != 4 or question.correct_index not in range(4):
            st.warning(f"Question {index + 1} was skipped because it is malformed.")
            continue
        st.markdown(f"**{index + 1}. {question.question}**")
        st.radio(
            "Choose one answer",
            options=question.options,
            key=f"quiz_answer_{index}",
            index=None,
            label_visibility="collapsed",
        )

    if st.session_state.get("quiz_score") is None:
        if st.button("Submit quiz", type="primary"):
            answers = {
                index: (
                    quiz.questions[index].options.index(
                        st.session_state[f"quiz_answer_{index}"]
                    )
                    if st.session_state.get(f"quiz_answer_{index}")
                    in quiz.questions[index].options
                    else None
                )
                for index in range(len(quiz.questions))
            }
            st.session_state["quiz_answers"] = answers
            st.session_state["quiz_score"] = score_quiz(quiz, answers)
            st.session_state["quiz_recommendations"] = revision_recommendations(quiz, answers)
            st.rerun()
        return

    score = st.session_state["quiz_score"]
    st.subheader("Results")
    st.metric(
        "Score",
        f"{score.percentage:.2f}%",
        f"{score.correct_count}/{score.valid_question_count} correct",
    )
    st.write(
        f"Answered {score.answered_count} of {score.valid_question_count}. "
        "Unanswered questions were counted as incorrect."
    )

    answers = st.session_state.get("quiz_answers", {})
    with st.expander("Review answers", expanded=True):
        for index, question in enumerate(quiz.questions):
            if len(question.options) != 4 or question.correct_index not in range(4):
                continue
            selected = answers.get(index)
            selected_text = question.options[selected] if selected is not None else "Unanswered"
            correct_text = question.options[question.correct_index]
            status = "Correct" if selected == question.correct_index else "Incorrect"
            st.markdown(f"**Question {index + 1}: {status}**")
            st.write(f"Selected answer: {selected_text}")
            st.write(f"Correct answer: {correct_text}")
            st.write(f"Explanation: {question.explanation}")
            st.caption(f"Lecture passage: {question.source_passage}")

    recommendations = st.session_state.get("quiz_recommendations", ())
    if recommendations:
        st.write("**Revision recommendations**")
        for recommendation in recommendations:
            st.markdown(f"- **Review:** {recommendation.question}")
            st.write(f"Correct answer: {recommendation.correct_answer}")
            st.write(f"Why: {recommendation.explanation}")
            st.caption(f"Lecture passage: {recommendation.source_passage}")

    if st.button("Retake quiz"):
        for index in range(len(quiz.questions)):
            st.session_state.pop(f"quiz_answer_{index}", None)
        for key in ("quiz", "quiz_answers", "quiz_score", "quiz_recommendations"):
            st.session_state.pop(key, None)
        st.rerun()


def main() -> None:
    _render_header()
    lecture = _render_input()
    if lecture is None:
        st.info("Choose a lecture source from the sidebar to get started.")
        return

    _render_lecture_metadata(lecture)
    analysis = st.session_state.get("analysis")
    if not analysis or analysis["source_text"] != lecture.text:
        if st.button("Generate summaries and study materials", type="primary"):
            _generate_analysis(lecture)
            analysis = st.session_state.get("analysis")
            if not analysis or analysis["source_text"] != lecture.text:
                return
        else:
            return

    tabs = st.tabs(["Summary", "Study materials", "Interactive quiz"])
    with tabs[0]:
        _render_summary(analysis)
    with tabs[1]:
        _render_study_materials(analysis)
    with tabs[2]:
        _render_quiz(lecture, analysis)


main()

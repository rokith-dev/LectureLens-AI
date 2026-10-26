import streamlit as st

from lecturelens.models import LectureText
from lecturelens.pdf_input import PdfInputError, extract_pdf_text
from lecturelens.quiz import QuizGenerationError, generate_quiz
from lecturelens.study_materials import (
    StudyMaterialsError,
    extract_keywords,
    generate_glossary,
    generate_study_notes,
)
from lecturelens.summarizer import LectureSummarizer, SummarizationError
from lecturelens.youtube_input import YouTubeInputError, fetch_youtube_transcript


@st.cache_resource
def get_summarizer() -> LectureSummarizer:
    return LectureSummarizer()


def render_study_materials(lecture: LectureText) -> None:
    analysis = st.session_state.get("analysis")
    if not analysis or analysis["source_text"] != lecture.text:
        return

    summaries = analysis["summaries"]
    keywords = analysis["keywords"]
    glossary = analysis["glossary"]
    notes = analysis["notes"]

    st.subheader("Short summary")
    st.write(summaries.short)
    st.subheader("Detailed summary")
    st.write(summaries.detailed)
    st.caption(f"Processed {summaries.chunk_count} lecture text chunk(s).")

    st.subheader("Study notes")
    st.write("**Overview**")
    st.write(notes.overview)
    st.write("**Main headings**")
    for heading in notes.headings:
        st.markdown(f"- {heading}")
    st.write("**Important concepts**")
    for concept in notes.important_concepts:
        st.markdown(f"- {concept}")
    st.write("**Notes**")
    for bullet in notes.bullet_points:
        st.markdown(f"- {bullet}")
    if notes.supported_definitions:
        st.write("**Definitions supported by the lecture**")
        for entry in notes.supported_definitions:
            st.markdown(f"- **{entry.term}:** {entry.definition}")
    if notes.examples:
        st.write("**Examples from the lecture**")
        for example in notes.examples:
            st.markdown(f"- {example}")
    st.write("**Key takeaways**")
    for takeaway in notes.key_takeaways:
        st.markdown(f"- {takeaway}")

    st.subheader("Keywords")
    for keyword in keywords:
        st.markdown(f"- **{keyword.phrase}** — relevance {keyword.score:.3f}")

    st.subheader("Glossary")
    for entry in glossary:
        verification = " *(needs verification)*" if entry.needs_verification else ""
        st.markdown(f"- **{entry.term}:** {entry.definition}{verification}")

    st.subheader("Quiz")
    question_count = st.selectbox(
        "Number of questions",
        options=(5, 10, 15),
        key="quiz_question_count",
    )
    if st.button("Generate quiz"):
        with st.spinner("Generating validated quiz questions..."):
            try:
                st.session_state["quiz"] = generate_quiz(
                    lecture.text,
                    question_count,
                    glossary,
                    keywords,
                )
                st.session_state.pop("quiz_error", None)
            except QuizGenerationError as error:
                st.session_state.pop("quiz", None)
                st.session_state["quiz_error"] = str(error)

    if st.session_state.get("quiz_error"):
        st.error(st.session_state["quiz_error"])
    quiz = st.session_state.get("quiz")
    if quiz:
        for index, question in enumerate(quiz.questions, start=1):
            st.markdown(f"**{index}. {question.question}**")
            for option_index, option in enumerate(question.options, start=1):
                st.markdown(f"{option_index}. {option}")
            st.caption(
                f"Correct answer: {question.correct_index + 1}. "
                f"{question.explanation}"
            )
            st.caption(f"Source: {question.source_passage}")
        if len(quiz.questions) < quiz.requested_count:
            st.info(
                f"Generated {len(quiz.questions)} validated question(s); "
                f"the lecture supported fewer than {quiz.requested_count}."
            )


st.set_page_config(page_title="LectureLens AI", page_icon="📚", layout="wide")
st.title("LectureLens AI")
st.write("Choose one supported lecture source to extract text and generate study materials.")

source = st.radio("Lecture input", ("PDF upload", "YouTube URL"), horizontal=True)
lecture: LectureText | None = None

if source == "PDF upload":
    uploaded_file = st.file_uploader("Upload a PDF lecture", type=["pdf"])
    if uploaded_file is not None:
        with st.spinner("Extracting text from the PDF..."):
            try:
                lecture = extract_pdf_text(uploaded_file.getvalue(), uploaded_file.name)
            except PdfInputError as error:
                st.error(str(error))
else:
    youtube_url = st.text_input("YouTube video URL", placeholder="https://www.youtube.com/watch?v=...")
    if youtube_url:
        with st.spinner("Retrieving available captions..."):
            try:
                lecture = fetch_youtube_transcript(youtube_url)
            except YouTubeInputError as error:
                st.error(str(error))

if lecture is not None:
    st.success("Lecture text extracted successfully.")
    st.write(f"**Source:** {lecture.title}")
    for key, value in lecture.metadata.items():
        st.caption(f"{key.replace('_', ' ').title()}: {value}")
    st.text_area("Extracted lecture text", lecture.text, height=500)

    if st.button("Generate summaries and study materials", type="primary"):
        with st.spinner("Generating summaries and study materials..."):
            try:
                summaries = get_summarizer().summarize(lecture.text)
                keywords = extract_keywords(lecture.text)
                glossary = generate_glossary(lecture.text, keywords)
                notes = generate_study_notes(
                    lecture.text,
                    summaries.short,
                    summaries.detailed,
                )
                st.session_state["analysis"] = {
                    "source_text": lecture.text,
                    "summaries": summaries,
                    "keywords": keywords,
                    "glossary": glossary,
                    "notes": notes,
                }
                st.session_state.pop("quiz", None)
                st.session_state.pop("quiz_error", None)
            except (SummarizationError, StudyMaterialsError) as error:
                st.error(str(error))

    render_study_materials(lecture)

import streamlit as st

from lecturelens.models import LectureText
from lecturelens.pdf_input import PdfInputError, extract_pdf_text
from lecturelens.summarizer import LectureSummarizer, SummarizationError
from lecturelens.study_materials import (
    StudyMaterialsError,
    extract_keywords,
    generate_glossary,
    generate_study_notes,
)
from lecturelens.youtube_input import YouTubeInputError, fetch_youtube_transcript


@st.cache_resource
def get_summarizer() -> LectureSummarizer:
    return LectureSummarizer()


st.set_page_config(page_title="LectureLens AI", page_icon="📚", layout="wide")
st.title("LectureLens AI")
st.write("Choose one supported lecture source to extract text and generate summaries.")

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

    if st.button("Generate summaries", type="primary"):
        with st.spinner("Generating short and detailed summaries..."):
            try:
                summaries = get_summarizer().summarize(lecture.text)
            except SummarizationError as error:
                st.error(str(error))
            else:
                st.subheader("Short summary")
                st.write(summaries.short)
                st.subheader("Detailed summary")
                st.write(summaries.detailed)
                st.caption(f"Processed {summaries.chunk_count} lecture text chunk(s).")
                with st.spinner("Generating study notes, keywords, and glossary..."):
                    try:
                        keywords = extract_keywords(lecture.text)
                        glossary = generate_glossary(lecture.text, keywords)
                        notes = generate_study_notes(
                            lecture.text,
                            summaries.short,
                            summaries.detailed,
                        )
                    except StudyMaterialsError as error:
                        st.error(str(error))
                    else:
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

import streamlit as st

from lecturelens.models import LectureText
from lecturelens.pdf_input import PdfInputError, extract_pdf_text
from lecturelens.youtube_input import YouTubeInputError, fetch_youtube_transcript


st.set_page_config(page_title="LectureLens AI", page_icon="📚", layout="wide")
st.title("LectureLens AI")
st.write("Choose one supported lecture source to extract readable text.")

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

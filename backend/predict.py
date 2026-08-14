import re
import nltk

from nltk.corpus import stopwords


# Download stopwords if not already installed
try:
    stop_words = set(stopwords.words("english"))
except LookupError:
    nltk.download("stopwords")
    stop_words = set(stopwords.words("english"))


def clean_text(text):

    # Convert to lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(
        r"http\S+|www\S+|https\S+",
        "",
        text
    )

    # Remove numbers and special characters
    text = re.sub(
        r"[^a-zA-Z\s]",
        "",
        text
    )

    # Split into words
    words = text.split()

    # Remove stopwords
    words = [
        word for word in words
        if word not in stop_words
    ]

    # Join words
    text = " ".join(words)

    return text
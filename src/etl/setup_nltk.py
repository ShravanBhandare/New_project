import nltk
import logging

logger = logging.getLogger(__name__)

def main():
    logger.info("Downloading NLTK VADER lexicon...")
    try:
        nltk.download('vader_lexicon', quiet=False)
        logger.info("NLTK VADER lexicon downloaded successfully.")
    except Exception as e:
        logger.error(f"Failed to download NLTK data: {e}")

if __name__ == "__main__":
    main()

from app.utils.logger import get_logger

logger = get_logger("test_logger")


def test_log():
    logger.info("This is an info log.")
    logger.warning("This is a warning log.")
    logger.error("This is an error log.")


if __name__ == "__main__":
    test_log()
    print("Logger test completed.")
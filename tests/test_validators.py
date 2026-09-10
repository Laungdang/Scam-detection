from app.utils.validators import detect_input_type


def test_detect_input_type():
    samples = [
        "0812345678",
        "123-4-56789-0",
        "https://example.com",
        "www.google.com",
        "รีบโอนเงินตอนนี้เลย"
    ]

    for sample in samples:
        print(sample, "->", detect_input_type(sample))


if __name__ == "__main__":
    test_detect_input_type()
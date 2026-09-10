from app.utils.input_processor import process_user_input


def test_processor():
    samples = [
        "081-234-5678",
        "123-4-56789-0",
        "https://example.com/login",
        "รีบโอนเงินตอนนี้เลย ของมีชิ้นเดียว!!!"
    ]

    for sample in samples:
        result = process_user_input(sample)
        print(result)


if __name__ == "__main__":
    test_processor()
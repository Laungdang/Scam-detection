from app.services.blacklist_service import check_blacklist


def test_blacklist_call():
    samples = [
        ("0812345678", "phone"),
        ("1234567890", "bank_account"),
        ("https://example.com", "url"),
    ]

    for value, value_type in samples:
        result = check_blacklist(value=value, value_type=value_type)
        print("=" * 50)
        print("VALUE:", value)
        print("TYPE:", value_type)
        print("RESULT:", result)


if __name__ == "__main__":
    test_blacklist_call()
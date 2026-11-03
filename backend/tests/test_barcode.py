from app.barcode import gs1_check_digit, is_valid_tote_barcode, make_tote_barcode


def test_gs1_check_digit_known_value():
    # EAN-13 4006381333931: body 400638133393, check digit 1
    assert gs1_check_digit("400638133393") == 1


def test_generated_barcode_is_valid():
    code = make_tote_barcode(42)
    assert code.startswith("PF000000042")
    assert len(code) == 12
    assert is_valid_tote_barcode(code)


def test_single_digit_error_is_detected():
    code = make_tote_barcode(12345)
    corrupted = code[:-2] + str((int(code[-2]) + 1) % 10) + code[-1]
    assert not is_valid_tote_barcode(corrupted)


def test_wrong_format_is_rejected():
    assert not is_valid_tote_barcode("XX0000000421")
    assert not is_valid_tote_barcode("PF123")

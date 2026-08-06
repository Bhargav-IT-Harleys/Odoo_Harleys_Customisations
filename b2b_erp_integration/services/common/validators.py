import re


def validate_mobile_number(number):
    if not number:
        raise ValueError("Mobile number is required.")
    normalized = str(number).strip()
    if not re.fullmatch(r"\d{10}", normalized):
        raise ValueError("Mobile number must contain exactly 10 digits.")
    return normalized


def validate_otp(otp):
    if not otp:
        raise ValueError("OTP is required.")
    normalized = str(otp).strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise ValueError("OTP must contain exactly 6 digits.")
    return normalized

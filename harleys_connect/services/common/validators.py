import re


def validate_otp(otp):
    if not otp:
        raise ValueError("OTP is required.")
    normalized = str(otp).strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise ValueError("OTP must contain exactly 6 digits.")
    return normalized

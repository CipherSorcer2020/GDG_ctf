from ctf_runner.flags import generate_flag, hash_flag, verify_flag


def test_generate_flag_format():
    flag = generate_flag()
    assert flag.startswith("flag{")
    assert flag.endswith("}")
    assert len(flag) == len("flag{}") + 16


def test_generate_flag_custom_prefix():
    assert generate_flag(prefix="ctf").startswith("ctf{")


def test_generate_flag_is_random():
    assert generate_flag() != generate_flag()


def test_verify_roundtrip():
    flag = generate_flag()
    assert verify_flag(flag, hash_flag(flag))


def test_verify_rejects_wrong_flag():
    flag = generate_flag()
    assert not verify_flag(generate_flag(), hash_flag(flag))


def test_verify_tolerates_whitespace():
    flag = generate_flag()
    assert verify_flag(f"  {flag}\n", hash_flag(flag))

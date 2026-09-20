from app.core.username import normalize_login_username


def test_normalize_removes_internal_spaces() -> None:
    assert normalize_login_username("owner. kamalrestro.921a") == "owner.kamalrestro.921a"


def test_normalize_trims_and_lowercases() -> None:
    assert normalize_login_username("  Owner.KamalRestro.921A  ") == "owner.kamalrestro.921a"

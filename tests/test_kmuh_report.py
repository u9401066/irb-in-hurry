"""KMUH report must fail closed until official assets are verified."""

from scripts.report_kmuh import main


def test_kmuh_report_is_not_green_with_unretrieved_assets(capsys):
    result = main()
    output = capsys.readouterr().out

    assert result == 1
    assert '"ready_for_official_generation": false' in output
    assert "kmuh_general_new" in output

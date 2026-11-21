import pytest

from app.reports.report_utils import create_pdf_buffer


@pytest.mark.parametrize(
    "farm_name",
    ["<b>unclosed", "a < b & c", '<img src="/etc/passwd">', "<para>"],
)
def test_pdf_handles_markup_characters(farm_name):
    buffer = create_pdf_buffer(
        title="Farm Report",
        subtitle=f"Farm: {farm_name}",
        headers=["Farm", "Area"],
        rows=[[farm_name, 2.5]],
    )

    assert buffer.getvalue().startswith(b"%PDF")


def test_csv_neutralizes_formulas():
    from app.reports.report_utils import create_csv_buffer

    buffer = create_csv_buffer(
        headers=["Farm", "Change"],
        rows=[['=HYPERLINK("http://evil","x")', -3.5], ["@SUM(A1)", 2]],
    )
    text = buffer.getvalue().decode("utf-8-sig")

    assert "'=HYPERLINK" in text
    assert "'@SUM(A1)" in text
    assert "-3.5000" in text
    assert "'-3.5000" not in text

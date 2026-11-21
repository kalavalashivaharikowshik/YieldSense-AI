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

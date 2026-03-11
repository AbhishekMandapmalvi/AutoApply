"""Tests for core/document_parser.py — TASK-030 M1.

Tests text extraction from PDF, DOCX, TXT, and MD files.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.document_parser import SUPPORTED_EXTENSIONS, extract_text


class TestExtractText:
    """Tests for extract_text() main function."""

    def test_txt_file(self, tmp_path):
        """TXT files are read directly."""
        f = tmp_path / "resume.txt"
        f.write_text("Senior Engineer at Acme Corp\n5 years experience", encoding="utf-8")
        result = extract_text(f)
        assert "Senior Engineer" in result
        assert "Acme Corp" in result

    def test_md_file(self, tmp_path):
        """MD files are read directly."""
        f = tmp_path / "notes.md"
        f.write_text("# Experience\n- Built REST APIs", encoding="utf-8")
        result = extract_text(f)
        assert "Built REST APIs" in result

    def test_file_not_found(self, tmp_path):
        """Missing files raise FileNotFoundError."""
        f = tmp_path / "nonexistent.txt"
        with pytest.raises(FileNotFoundError):
            extract_text(f)

    def test_unsupported_extension(self, tmp_path):
        """Unsupported file types raise ValueError."""
        f = tmp_path / "data.csv"
        f.write_text("a,b,c", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_text(f)

    def test_supported_extensions_constant(self):
        """SUPPORTED_EXTENSIONS contains expected types."""
        assert ".pdf" in SUPPORTED_EXTENSIONS
        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".txt" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS

    def test_latin1_fallback(self, tmp_path):
        """Latin-1 encoded files are handled when UTF-8 fails."""
        f = tmp_path / "legacy.txt"
        f.write_bytes(b"R\xe9sum\xe9 of John")
        result = extract_text(f)
        assert "sum" in result  # latin-1 decoded

    @patch("core.document_parser._extract_from_pdf")
    def test_pdf_dispatched(self, mock_pdf, tmp_path):
        """PDF files dispatch to _extract_from_pdf."""
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 fake")
        mock_pdf.return_value = "PDF content"
        result = extract_text(f)
        mock_pdf.assert_called_once_with(f)
        assert result == "PDF content"

    @patch("core.document_parser._extract_from_docx")
    def test_docx_dispatched(self, mock_docx, tmp_path):
        """DOCX files dispatch to _extract_from_docx."""
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK fake docx")
        mock_docx.return_value = "DOCX content"
        result = extract_text(f)
        mock_docx.assert_called_once_with(f)
        assert result == "DOCX content"


class TestPdfExtraction:
    """Tests for PDF extraction via PyPDF2."""

    def test_pdf_extraction_with_mock(self, tmp_path):
        """PDF extraction calls PyPDF2.PdfReader."""
        f = tmp_path / "test.pdf"
        f.write_bytes(b"fake pdf")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("PyPDF2.PdfReader", return_value=mock_reader):
            from core.document_parser import _extract_from_pdf
            result = _extract_from_pdf(f)
            assert result == "Page 1 content"

    def test_pdf_import_error(self, tmp_path):
        """Missing PyPDF2 raises RuntimeError."""
        f = tmp_path / "test.pdf"
        f.write_bytes(b"fake pdf")

        with patch.dict("sys.modules", {"PyPDF2": None}):
            with pytest.raises((RuntimeError, ImportError)):
                from core.document_parser import _extract_from_pdf
                _extract_from_pdf(f)


class TestDocxExtraction:
    """Tests for DOCX extraction."""

    def test_docx_import_error(self, tmp_path):
        """Missing python-docx raises RuntimeError."""
        f = tmp_path / "test.docx"
        f.write_bytes(b"fake docx")

        with patch.dict("sys.modules", {"docx": None}):
            with pytest.raises((RuntimeError, ImportError)):
                from core.document_parser import _extract_from_docx
                _extract_from_docx(f)

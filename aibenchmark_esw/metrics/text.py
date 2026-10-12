"""Escape report labels and spreadsheet cells at the export boundary."""
import html


def markdown_text(value):
    return (html.escape(str(value), quote=False).replace('\\', '\\\\').replace('`', '\\`')
            .replace('|', '\\|').replace('\r', ' ').replace('\n', ' '))


def csv_safe_row(row):
    def cell(value):
        if isinstance(value, str) and (value.startswith(('\t', '\r', '\n'))
                                       or value.lstrip().startswith(('=', '+', '-', '@'))):
            return "'" + value
        return value
    return {key: cell(value) for key, value in row.items()}

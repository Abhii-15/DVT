from datetime import datetime


def summarize_test_rows(rows):
    summary = {'total': len(rows), 'pass': 0, 'fail': 0, 'error': 0}
    for row in rows:
        result = str(row.get('Result', '')).lower()
        if 'pass' in result:
            summary['pass'] += 1
        elif 'fail' in result:
            summary['fail'] += 1
        elif 'error' in result:
            summary['error'] += 1
    return summary


def build_test_report(rows):
    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'summary': summarize_test_rows(rows),
        'results': rows,
    }


def render_html_report(report):
    summary = report['summary']
    items = []
    for row in report['results']:
        items.append(
            f"<tr><td>{row.get('name', '')}</td><td>{row.get('status', '')}</td><td>{row.get('result', '')}</td></tr>"
        )
    return (
        '<html><head><meta charset="utf-8"><style>'
        'body{font-family:Segoe UI,Arial,sans-serif;background:#10161d;color:#e8eef4;padding:20px;}'
        'table{border-collapse:collapse;width:100%;}td,th{border:1px solid #31465d;padding:8px;text-align:left;}'
        'th{background:#1b2a38;} .summary{display:flex;gap:20px;margin-bottom:12px;}'
        '</style></head><body>'
        f'<h1>CANoe Test Report</h1><p>Generated: {report["generated_at"]}</p>'
        f'<div class="summary"><div>Total: {summary["total"]}</div><div>Pass: {summary["pass"]}</div><div>Fail: {summary["fail"]}</div><div>Error: {summary["error"]}</div></div>'
        '<table><thead><tr><th>Test</th><th>Status</th><th>Result</th></tr></thead><tbody>'
        + ''.join(items)
        + '</tbody></table></body></html>'
    )
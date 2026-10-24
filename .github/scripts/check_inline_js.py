"""Syntax-check inline JavaScript in index.html with Node.js."""
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import tempfile


class InlineScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.current = None
        self.external = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            attrs = dict(attrs)
            self.external = bool(attrs.get("src"))
            self.current = [] if not self.external else None

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            if self.current is not None:
                code = "".join(self.current).strip()
                if code:
                    self.scripts.append(code)
            self.current = None
            self.external = False


html = Path("index.html").read_text(encoding="utf-8")
parser = InlineScripts()
parser.feed(html)
if not parser.scripts:
    raise SystemExit("No inline JavaScript found to check")
with tempfile.TemporaryDirectory() as temp_dir:
    for index, code in enumerate(parser.scripts, start=1):
        path = Path(temp_dir) / f"inline-{index}.js"
        path.write_text(code, encoding="utf-8")
        subprocess.run(["node", "--check", str(path)], check=True)
print(f"Syntax checked {len(parser.scripts)} inline JavaScript block(s).")

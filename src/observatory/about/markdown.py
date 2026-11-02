"""Small, dependency-free Markdown subset renderer (headings, lists, tables, code, emphasis, links)."""

from __future__ import annotations

import html
import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+\{#([\w-]+)\})?\s*$")


def inline(text: str) -> str:
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|/[^)\s]*)\)", r'<a href="\2">\1</a>', t)
    return t


def render(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("<") and line.rstrip().endswith(">"):  # trusted, pre-rendered HTML block
            flush_para()
            out.append(line)
        elif line.startswith("```"):
            flush_para()
            lang = line[3:].strip()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>")
            i = j
        elif m := _HEADING.match(line):
            flush_para()
            level, text, anchor = len(m.group(1)), m.group(2), m.group(3)
            aid = f' id="{anchor}"' if anchor else ""
            out.append(f"<h{level}{aid}>{inline(text)}</h{level}>")
        elif line.startswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            i -= 1
            head, body = rows[0], [r for r in rows[1:] if not all(set(c) <= set("-: ") for c in r)]
            out.append(
                '<div class="table-wrap"><table><thead><tr>'
                + "".join(f'<th scope="col">{inline(c)}</th>' for c in head)
                + "</tr></thead><tbody>"
            )
            out += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body]
            out.append("</tbody></table></div>")
        elif re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            flush_para()
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and (
                re.match(r"^\s*[-*]\s+", lines[i])
                or re.match(r"^\s*\d+\.\s+", lines[i])
                or (lines[i].startswith("  ") and lines[i].strip())
            ):
                if lines[i].startswith("  ") and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                    items[-1] += " " + lines[i].strip()
                else:
                    items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            i -= 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(it)}</li>" for it in items) + f"</{tag}>")
        elif not line.strip():
            flush_para()
        else:
            para.append(line.strip())
        i += 1
    flush_para()
    return "\n".join(out)

# -*- coding: utf-8 -*-
"""把 plan 下的规划文档转成单文件 HTML（无外部依赖、可直接双击打开）。

用法：
    python plan/tools/md2html.py "plan/07-柏氏规则细则.md"
    python plan/tools/md2html.py plan/*.md --out-dir tmp_html

支持的 Markdown 子集：ATX 标题、段落、无序/有序列表（含一层缩进嵌套）、
管道表格、围栏代码块、引用块、分隔线、行内代码/加粗/链接。
"""
import argparse
import io
import os
import re

CSS = """
:root{--ink:#17211C;--muted:#5C6B63;--line:#DDE5E0;--accent:#0F3D2E;--accent2:#C9A063;--bg:#FFFFFF;--soft:#F7FAF8;}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
 font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;}
.page{max-width:1080px;margin:0 auto;padding:40px 28px 96px}
h1{font-size:30px;line-height:1.3;margin:0 0 8px;color:var(--accent);letter-spacing:.5px}
h1::after{content:"";display:block;width:64px;height:4px;background:var(--accent2);margin-top:14px;border-radius:2px}
h2{font-size:22px;margin:52px 0 14px;padding-left:12px;border-left:5px solid var(--accent2);line-height:1.4}
h3{font-size:17px;margin:30px 0 10px;color:var(--accent)}
h4{font-size:15px;margin:22px 0 8px;color:var(--muted)}
p{margin:12px 0}
a{color:#146C50;text-decoration:none;border-bottom:1px solid rgba(20,108,80,.28)}
a:hover{border-bottom-color:#146C50}
strong{color:#0B2A1F}
ul,ol{margin:12px 0;padding-left:24px}
li{margin:6px 0}
li>ul,li>ol{margin:6px 0}
code{background:var(--soft);border:1px solid var(--line);border-radius:4px;
 padding:1px 5px;font-family:"JetBrains Mono",Consolas,"Courier New",monospace;font-size:13.5px;color:#0B3B2C}
pre{background:#0F3D2E;color:#E8F1EC;border-radius:10px;padding:16px 18px;overflow:auto;margin:16px 0;
 box-shadow:inset 0 0 0 1px rgba(255,255,255,.06)}
pre code{background:none;border:0;color:inherit;padding:0;font-size:13px;line-height:1.6}
blockquote{margin:16px 0;padding:10px 16px;background:#FCFAF3;border-left:4px solid var(--accent2);
 border-radius:0 8px 8px 0;color:var(--muted)}
blockquote p{margin:4px 0;font-size:14.5px}
.table-wrap{overflow-x:auto;margin:16px 0;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:14.5px;background:#fff}
th,td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--line)}
th{background:var(--accent);color:#F6EFDC;font-weight:600;white-space:nowrap;border-bottom:0}
tbody tr:nth-child(even){background:#FAFCFA}
tbody tr:hover{background:#F2F8F4}
tbody tr:last-child td{border-bottom:0}
hr{border:0;border-top:1px solid var(--line);margin:36px 0}
.toc{margin:28px 0 8px;border:1px solid var(--line);border-radius:10px;background:var(--soft);padding:12px 18px}
.toc summary{cursor:pointer;font-weight:600;color:var(--accent);outline:none}
.toc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:6px 18px;margin-top:10px}
.toc-grid a{font-size:14px;border:0;color:#33544A}
.toc-grid a:hover{color:#146C50;text-decoration:underline}
.meta{color:var(--muted);font-size:13px;margin-top:10px}
@media (max-width:640px){.page{padding:24px 16px 64px}h1{font-size:24px}h2{font-size:19px;margin-top:38px}}
@media print{body{font-size:12pt}.toc{display:none}pre{background:#F5F5F5;color:#111;box-shadow:none}h2{page-break-after:avoid}table{page-break-inside:avoid}}
"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def convert(md_text):
    lines = md_text.splitlines()
    n = len(lines)

    def inline(s):
        codes = []

        def stash(m):
            codes.append("<code>" + esc(m.group(1)) + "</code>")
            return "\x00%d\x00" % (len(codes) - 1)

        s = re.sub(r"`([^`]*)`", stash, s)
        s = s.replace("\\|", "|")
        s = esc(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)

    def is_list_line(raw):
        return bool(re.match(r"^\s*([-*]|\d+[.)])\s+\S", raw))

    def indent_of(raw):
        return len(raw) - len(raw.lstrip())

    def split_row(line):
        s = line.strip()
        if s.startswith("|"):
            s = s[1:]
        if s.endswith("|"):
            s = s[:-1]
        return [c.strip() for c in re.split(r"(?<!\\)\|", s)]

    def is_table_start(idx):
        if idx + 1 >= n or not lines[idx].strip().startswith("|"):
            return False
        return bool(re.match(r"^\|[\s:\-|]+\|\s*$", lines[idx + 1].strip()))

    def parse_list(start, indent):
        tag = "ol" if re.match(r"^\s*\d+[.)]\s", lines[start]) else "ul"
        items = []
        i = start
        while i < n:
            raw = lines[i]
            if not raw.strip():
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and is_list_line(lines[j]) and indent_of(lines[j]) == indent:
                    i = j
                    continue
                break
            if not is_list_line(raw):
                break
            ind = indent_of(raw)
            if ind > indent:
                child, i = parse_list(i, ind)
                if items:
                    items[-1][1].append(child)
                continue
            if ind < indent:
                break
            cur_tag = "ol" if re.match(r"^\s*\d+[.)]\s", raw) else "ul"
            if cur_tag != tag:
                break
            m = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$", raw)
            items.append([inline(m.group(1)), []])
            i += 1
        html = "<%s>" % tag
        for content, children in items:
            html += "<li>" + content + "".join(children) + "</li>"
        return html + "</%s>" % tag, i

    out, toc = [], []
    i = 0
    title = ""
    h2 = 0
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if not s:
            i += 1
            continue

        if s.startswith("```"):
            lang = s[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = ' class="language-%s"' % lang if lang else ""
            out.append("<pre><code%s>%s</code></pre>" % (cls, esc("\n".join(buf))))
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            txt = inline(m.group(2))
            plain = re.sub(r"<[^>]+>", "", txt)
            if lvl == 1 and not title:
                title = plain
            if lvl == 2:
                h2 += 1
                anchor = "sec-%d" % h2
                toc.append((anchor, plain))
                out.append('<h2 id="%s">%s</h2>' % (anchor, txt))
            else:
                out.append("<h%d>%s</h%d>" % (lvl, txt, lvl))
            i += 1
            continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            out.append("<blockquote>%s</blockquote>" % "".join("<p>%s</p>" % inline(x) for x in buf if x))
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            out.append("<hr>")
            i += 1
            continue

        if is_table_start(i):
            header = split_row(lines[i])
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            t = ['<div class="table-wrap"><table><thead><tr>']
            t += ["<th>%s</th>" % inline(c) for c in header]
            t.append("</tr></thead><tbody>")
            for r in rows:
                t.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue

        if is_list_line(raw):
            html, i = parse_list(i, indent_of(raw))
            out.append(html)
            continue

        buf = []
        while i < n:
            cs = lines[i].strip()
            if not cs or cs.startswith(("```", ">", "#")):
                break
            if re.match(r"^(-{3,}|\*{3,}|_{3,})$", cs):
                break
            if is_table_start(i) or is_list_line(lines[i]):
                break
            buf.append(cs)
            i += 1
        if buf:
            out.append("<p>%s</p>" % inline("".join(buf)))

    return title, toc, "\n".join(out)


def build(md_path, out_path):
    src = io.open(md_path, encoding="utf-8").read()
    title, toc, body = convert(src)
    toc_html = "".join('<a href="#%s">%s</a>' % (a, t) for a, t in toc)
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
<style>%s</style>
</head>
<body>
<div class="page">
<details class="toc" open>
<summary>目录（%d 节）</summary>
<div class="toc-grid">%s</div>
</details>
%s
<p class="meta">由 <code>%s</code> 生成</p>
</div>
</body>
</html>
""" % (esc(title or os.path.basename(md_path)), CSS, len(toc), toc_html, body,
       os.path.basename(md_path))
    io.open(out_path, "w", encoding="utf-8", newline="\n").write(html)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Markdown → 单文件 HTML")
    ap.add_argument("sources", nargs="+", help="待转换的 .md 文件")
    ap.add_argument("--out-dir", default=None, help="输出目录，默认与源文件同目录")
    args = ap.parse_args()
    for src in args.sources:
        out_dir = args.out_dir or os.path.dirname(src) or "."
        if args.out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        out = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + ".html")
        build(src, out)
        print("written:", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()

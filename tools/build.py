#!/usr/bin/env python3
"""Narzedzie wydan repozytorium fzp_mcp_skills.

  python tools/build.py            aktualizuje w SKILL.md blok LIB (wersja, SHA-256, URL pobrania)
  python tools/build.py --check    konczy sie bledem, jesli blok LIB jest nieaktualny (CI)
  python tools/build.py --zip      dodatkowo buduje dist/<skill>.zip do wgrania jako skill
  python tools/build.py --tag      wypisuje oczekiwany tag wydania dla kazdego skilla

Konfiguracja: tools/release.json.
"""
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "tools", "release.json"), encoding="utf-8"))
BEGIN = "<!-- LIB:BEGIN (generowane przez tools/build.py - nie edytuj recznie) -->"
END = "<!-- LIB:END -->"

INSTALL = '''```python
import os, hashlib, subprocess, urllib.request
VER = "{ver}"
SHA = "{sha}"
URL = "{url}"
D = os.path.join(os.path.expanduser("~"), "{install_dir}")
P = os.path.join(D, "{lib_stem}_%s.py" % VER)
h = lambda b: hashlib.sha256(b).hexdigest()
ok = os.path.exists(P) and h(open(P, "rb").read()) == SHA
if ok:
    print("LIB_OK zainstalowana", P)
else:
    b, err = None, []
    try:
        b = urllib.request.urlopen(URL, timeout=30).read()
    except Exception as e:
        err.append("urllib: %s" % e)
        try:  # np. Python bez certyfikatow na macOS - systemowy curl ma certyfikaty systemu
            b = subprocess.run(["curl", "-fsSL", "--max-time", "30", URL], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
        except Exception as e2:
            err.append("curl: %s" % e2)
    if b is None:
        print("LIB_BLAD_POBRANIA", " | ".join(err))
    elif h(b) != SHA:
        print("LIB_ZLY_HASH", h(b))
    else:
        os.makedirs(D, exist_ok=True)
        open(P, "wb").write(b)
        print("LIB_OK pobrana", P)
        ok = True
if ok:  # {post_comment}
    exec(open(P, encoding="utf-8").read(), globals())
{post}
```

Nagłówek każdego kolejnego skryptu (`run_script_unsafe`):
```python
import os
exec(open(os.path.join(os.path.expanduser("~"), "{install_dir}", "{lib_stem}_{ver}.py"), encoding="utf-8").read(), globals())
W = "<folder roboczy>"
```'''


def lib_info(skill, spec):
    path = os.path.join(ROOT, "skills", skill, spec["lib"])
    data = open(path, "rb").read()
    if b"\r\n" in data:
        sys.exit("BLAD: %s ma konce linii CRLF - hash bylby rozny na roznych systemach" % path)
    m = re.search(rb'^LIB_VERSION = "([\d.]+)"', data, re.M)
    if not m:
        sys.exit("BLAD: brak LIB_VERSION w " + path)
    ver = m.group(1).decode()
    tag = spec["tag_prefix"] + ver
    url = "https://raw.githubusercontent.com/%s/%s/%s/skills/%s/%s" % (CFG["owner"], CFG["repo"], tag, skill, spec["lib"])
    return dict(ver=ver, sha=hashlib.sha256(data).hexdigest(), url=url, tag=tag, install_dir=spec["install_dir"],
                lib_stem=os.path.splitext(os.path.basename(spec["lib"]))[0], post_comment=spec["post_comment"],
                post="\n".join("    " + l for l in spec["post"]))


def render_block(info):
    return BEGIN + "\n" + INSTALL.format(**info) + "\n" + END


def update(skill, spec, check):
    info = lib_info(skill, spec)
    md_path = os.path.join(ROOT, "skills", skill, "SKILL.md")
    md = open(md_path, encoding="utf-8").read()
    a, b = md.find(BEGIN), md.find(END)
    if a < 0 or b < 0:
        sys.exit("BLAD: brak znacznikow LIB w " + md_path)
    new = md[:a] + render_block(info) + md[b + len(END):]
    # wersja w tytule SKILL.md
    new = re.sub(r"^(# .*\(wersja )[\d.]+(\))", r"\g<1>%s\2" % info["ver"], new, count=1, flags=re.M)
    if check:
        if new != md:
            sys.exit("BLAD: %s nieaktualny - uruchom: python tools/build.py" % md_path)
        print("OK %s %s sha256=%s" % (skill, info["ver"], info["sha"][:12]))
    else:
        if new != md:
            open(md_path, "w", encoding="utf-8", newline="\n").write(new)
            print("zaktualizowano", md_path)
        else:
            print("bez zmian", md_path)
    return info


def make_zip(skill):
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", skill + ".zip")
    base = os.path.join(ROOT, "skills", skill)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(base):
            dn[:] = sorted(d for d in dn if d not in ("__pycache__",))
            for f in sorted(fn):
                if f.endswith(".pyc") or f == ".DS_Store":
                    continue
                full = os.path.join(dp, f)
                z.write(full, os.path.join(skill, os.path.relpath(full, base)))
    print("zbudowano", out)
    return out


def main(argv):
    check, zip_, tag = "--check" in argv, "--zip" in argv, "--tag" in argv
    release = argv[argv.index("--release") + 1] if "--release" in argv else None
    matched = []
    for skill, spec in CFG["skills"].items():
        info = update(skill, spec, check or bool(release))
        if tag:
            print("TAG", skill, info["tag"])
        if zip_:
            make_zip(skill)
        if release and info["tag"] == release:
            matched.append((skill, info))
    if release:
        # wydanie jednego skilla: tag musi odpowiadac LIB_VERSION dokladnie jednego skilla
        if len(matched) != 1:
            sys.exit("BLAD: tag %s nie odpowiada wersji biblioteki zadnego skilla (zob. --tag)" % release)
        skill, info = matched[0]
        out = make_zip(skill)
        gh = os.environ.get("GITHUB_OUTPUT")
        if gh:
            with open(gh, "a") as f:
                f.write("skill=%s\nzip=%s\nurl=%s\nsha=%s\nver=%s\n" % (skill, out, info["url"], info["sha"], info["ver"]))


if __name__ == "__main__":
    main(sys.argv[1:])

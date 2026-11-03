# katalog_lib - biblioteka skilla "fzp-katalog-wypowiedzi". Nie edytuj recznie.
# Rdzen (transkrypcja, jednostki, skladanie timeline'u) wspolny z narracja_lib 1.0.
# Copyright (c) 2026 Marcin / Filmowanie z Profitem (filmowaniezprofitem.pl)
# Licencja: MIT + Commons Clause (zob. LICENSE w repozytorium fzp_mcp_skills)
import json, os, re, sys, time

LIB_VERSION = "1.0"
MARKER_TAG = "fzp-katalog"
MARKER_COLOR = "Cyan"
MIN_RESOLVE = (21, 1)
TC_DF = False
# AppendToTimeline: endFrame wylaczny (sprawdzone w Resolve 21.1). Weryfikowane po kazdym dodaniu w build_timeline().
END_EXCLUSIVE = True

SENT_END = re.compile(r"[.?!…]+[\"”»)]*$")
ABBR = set("np. itd. itp. tzn. tj. dr. prof. inż. mgr. ul. godz. min. ok. tys. mln. mld. zł. r. w. nr. św. ks.".split())


# ---------------------------------------------------------------- czas
def exact_fps(f):
    f = float(f)
    for n, d in ((24000, 1001), (30000, 1001), (48000, 1001), (60000, 1001), (120000, 1001)):
        if abs(f - n / d) < 0.005:
            return n / d
    return f


def tc2f(tc, fps, df=False):
    nom = int(round(fps))
    df = df or (";" in tc)
    h, m, s, f = [int(x) for x in re.split(r"[:;.]", tc.strip())]
    total = ((h * 60 + m) * 60 + s) * nom + f
    if df and nom in (30, 60):
        drop = 2 if nom == 30 else 4
        tm = h * 60 + m
        total -= drop * (tm - tm // 10)
    return total


def f2tc(fr, fps, df=None):
    nom = int(round(fps))
    fr = int(fr)
    df = TC_DF if df is None else df
    sep = ":"
    if df and nom in (30, 60):
        drop = 2 if nom == 30 else 4
        per10, per1 = nom * 600 - drop * 9, nom * 60 - drop
        d, m = divmod(fr, per10)
        fr += drop * 9 * d + (drop * ((m - drop) // per1) if m > drop else 0)
        sep = ";"
    s, f = divmod(fr, nom)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return "%02d:%02d:%02d%s%02d" % (h, m, s, sep, f)


def fmt_s(sec):
    return ("%.1f s" % sec).replace(".", ",")


def plural(n, one, few, many):
    """Polska odmiana: 1 sekcja, 2-4 sekcje, 5+ sekcji (12-14 -> sekcji)."""
    if n == 1:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def fmt_mmss(sec):
    sec = int(round(sec))
    return "%d:%02d" % divmod(sec, 60)


# ---------------------------------------------------------------- srodowisko i pliki
def check_env(resolve):
    v, prod = "", ""
    try:
        v = resolve.GetVersionString() or ""
    except Exception:
        pass
    try:
        prod = resolve.GetProductName() or ""
    except Exception:
        pass
    nums = tuple(int(x) for x in re.findall(r"\d+", v)[:2]) or (0, 0)
    ok, reason = True, ""
    if nums < MIN_RESOLVE:
        ok, reason = False, "wymagany DaVinci Resolve Studio %d.%d lub nowszy (jest: %s)" % (MIN_RESOLVE + (v or "?",))
    elif prod and "studio" not in prod.lower():
        ok, reason = False, "wymagana wersja Studio (jest: %s)" % prod
    return dict(ok=ok, version=v, product=prod, reason=reason, lib=LIB_VERSION, platform=sys.platform)


def safe_name(t):
    return re.sub(r"[^\w\-]+", "_", t).strip("_") or "projekt"


def new_workdir(project):
    base = os.path.join(os.path.expanduser("~"), ".fzp-katalog-wypowiedzi", "work")
    w = os.path.join(base, "%s_%s" % (safe_name(project.GetName()), time.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(w, exist_ok=True)
    return w


def _load(w, name):
    return json.load(open(os.path.join(w, name), encoding="utf-8"))


def _dump(w, name, obj):
    json.dump(obj, open(os.path.join(w, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- media pool
def _walk(folder, path, out):
    out.append((path, folder))
    for s in folder.GetSubFolderList() or []:
        _walk(s, path + [s.GetName()], out)
    return out


def _folders(mp):
    return _walk(mp.GetRootFolder(), [], [])


def _folder_by_path(mp, path):
    for p, f in _folders(mp):
        if p == list(path or []):
            return f
    return None


def _has_audio(c):
    t = (c.GetClipProperty("Type") or "")
    return "Audio" in t or "Multicam" in t


def _all_clips(mp):
    out = []
    for _, f in _folders(mp):
        out += f.GetClipList() or []
    return out


def clip_by_uid(project, uid):
    for c in _all_clips(project.GetMediaPool()):
        if c.GetUniqueId() == uid:
            return c
    return None


def list_bins(project):
    """Foldery Media Poola z liczba klipow z dzwiekiem (do wyboru binu z wypowiedziami)."""
    mp = project.GetMediaPool()
    cur = mp.GetCurrentFolder()
    out = []
    for p, f in _folders(mp):
        clips = [c for c in (f.GetClipList() or []) if _has_audio(c)]
        if clips:
            out.append(dict(path="/".join(p) or "(Master)", clips=len(clips),
                            current=f.GetUniqueId() == cur.GetUniqueId()))
    return out


def inventory(project, w, bin_path=None, recursive=False):
    """Klipy z dzwiekiem we wskazanym binie (sciezka 'A/B' albo biezacy folder). Zapisuje clips.json, zwraca liste."""
    mp = project.GetMediaPool()
    folder = mp.GetCurrentFolder() if not bin_path else _folder_by_path(mp, [] if bin_path == "(Master)" else bin_path.split("/"))
    if folder is None:
        raise RuntimeError("Nie ma binu: %s" % bin_path)
    src = [x for _, x in _walk(folder, [], [])] if recursive else [folder]
    clips = []
    for f in src:
        clips += [c for c in (f.GetClipList() or []) if _has_audio(c)]
    clips.sort(key=lambda c: c.GetName())
    out = []
    for i, c in enumerate(clips, 1):
        fps = exact_fps(c.GetClipProperty("FPS") or 25)
        marks = {}
        try:
            marks = (c.GetMarkInOut() or {}).get("audio") or (c.GetMarkInOut() or {}).get("video") or {}
        except Exception:
            pass
        out.append(dict(id="C%02d" % i, uid=c.GetUniqueId(), name=c.GetName(), fps=fps,
                        start_tc=c.GetClipProperty("Start TC") or "00:00:00:00",
                        frames=int(c.GetClipProperty("Frames") or 0), path=c.GetClipProperty("File Path") or "",
                        duration=c.GetClipProperty("Duration") or "", mark_in=marks.get("in"), mark_out=marks.get("out"),
                        transcribed=bool(((c.GetTranscription() or {}).get("segments")))))
    _dump(w, "clips.json", dict(bin=bin_path or "(biezacy)", clips=out,
                                tl_fps=float(project.GetSetting("timelineFrameRate") or 25)))
    return out


# ---------------------------------------------------------------- transkrypcja
def _transcription(project, info):
    """Transkrypcja klipu albo innego klipu z tego samego pliku (subclipy dziela plik, a Resolve i tak
    transkrybuje caly plik, ignorujac In/Out)."""
    c = clip_by_uid(project, info["uid"])
    tr = c.GetTranscription() if c else None
    if tr and tr.get("segments"):
        return tr
    for o in _all_clips(project.GetMediaPool()):
        if info["path"] and o.GetClipProperty("File Path") == info["path"]:
            t = o.GetTranscription()
            if t and t.get("segments"):
                return t
    return None


def transcribe_step(resolve, project, w, lang="pl", wait_s=50, poll_s=5):
    """Transkrybuje po kolei klipy bez transkrypcji (jeden plik = jedna transkrypcja). Wywoluj w petli, az zwroci
    status 'gotowe'. Czeka do wait_s w jednym wywolaniu."""
    meta = _load(w, "clips.json")
    st_path = os.path.join(w, "transcribe.json")
    st = _load(w, "transcribe.json") if os.path.exists(st_path) else dict(lang_before=project.GetSetting("transcriptionLanguage"), started=[])
    if project.GetSetting("transcriptionLanguage") != lang:
        project.SetSetting("transcriptionLanguage", lang)
    if resolve.GetCurrentPage() != "edit":
        st.setdefault("page_before", resolve.GetCurrentPage())
        resolve.OpenPage("edit")
    t0 = time.time()
    while True:
        js = project.GetTranscribeAudioStatus() or {}
        busy = js.get("JobStatus") in ("Initializing", "Analyzing", "Cancelling")
        if not busy:
            started_paths = {c["path"] for c in meta["clips"] if c["uid"] in st["started"]}
            todo = [c for c in meta["clips"] if c["uid"] not in st["started"] and c["path"] not in started_paths
                    and not _transcription(project, c)]
            if not todo:
                missing = [c["id"] for c in meta["clips"] if not _transcription(project, c)]
                _dump(w, "transcribe.json", st)
                return dict(status="gotowe" if not missing else "bledy", missing=missing, error=js.get("Error"))
            c = clip_by_uid(project, todo[0]["uid"])
            ok = c.TranscribeAudio(True, False)
            st["started"].append(todo[0]["uid"])
            _dump(w, "transcribe.json", st)
            if not ok:
                return dict(status="blad", clip=todo[0]["id"], error="TranscribeAudio zwrocilo False")
        if time.time() - t0 >= wait_s:
            done = sum(1 for c in meta["clips"] if _transcription(project, c))
            return dict(status="w toku", done=done, total=len(meta["clips"]),
                        percent=js.get("CompletionPercentage"), eta_s=js.get("EstimatedTimeRemaining"))
        time.sleep(poll_s)


def restore(resolve, project, w):
    """Przywraca jezyk transkrypcji i strone sprzed skilla."""
    p = os.path.join(w, "transcribe.json")
    if not os.path.exists(p):
        return []
    st = _load(w, "transcribe.json")
    if st.get("lang_before") is not None:
        project.SetSetting("transcriptionLanguage", st["lang_before"])
    if st.get("page_before"):
        resolve.OpenPage(st["page_before"])
    return ["przywrocono jezyk transkrypcji i strone"]


# ---------------------------------------------------------------- jednostki (zdania)
def _sentence_end(t):
    return bool(SENT_END.search(t)) and t.lower() not in ABBR


def _norm(t):
    return re.sub(r"[^\w]", "", t.lower())


def fix_stretched(words, fps):
    """Pierwsze slowo po ciszy bywa rozciagniete na cala cisze: koniec jest wiarygodny, start skracamy."""
    for w in words:
        if not w.get("first"):
            continue
        n = max(1, len(re.sub(r"[^\w]", "", w["t"])))
        if (w["e"] - w["s"]) * 1000.0 / fps > max(400, 150 * n):
            w["s"] = w["e"] - max(1, int(round(max(200, 80 * n) / 1000.0 * fps)))


def export_units(project, w, pause_s=1.5, max_s=20.0):
    """Z transkrypcji tworzy jednostki = zdania (dzielone tez przy zmianie mowcy i pauzie > pause_s).
    Zapisuje units.json. Zwraca liczbe jednostek na klip."""
    meta = _load(w, "clips.json")
    units, counts = {}, {}
    for c in meta["clips"]:
        tr = _transcription(project, c)
        if not tr:
            counts[c["id"]] = 0
            continue
        fps = c["fps"]
        c0 = tc2f(c["start_tc"], fps)
        lo = c["mark_in"] if c.get("mark_in") is not None else 0
        hi = c["mark_out"] if c.get("mark_out") is not None else 10 ** 9
        words = []
        for seg in tr.get("segments") or []:
            first = True
            for wd in seg.get("words") or []:
                t = (wd.get("text") or "").strip()
                if not t or t == "(...)" or not re.search(r"\w", t):  # cisza albo sama interpunkcja ("...")
                    first = True
                    continue
                s, e = tc2f(wd["start"], fps) - c0, tc2f(wd["end"], fps) - c0
                words.append(dict(t=t, s=s, e=max(e, s + 1), sp=seg.get("speaker") or "S1", first=first))
                first = False
        fix_stretched(words, fps)
        words = [x for x in words if x["s"] >= lo and x["e"] <= hi + 1]
        cu, n = [], 0
        for i, x in enumerate(words):
            if cu:
                p = words[i - 1]
                if (_sentence_end(p["t"]) or p["sp"] != x["sp"] or (x["s"] - p["e"]) > pause_s * fps
                        or (x["s"] - cu[0]["s"]) > max_s * fps and p["t"][-1:] in ",;:–"):
                    n += 1
                    units["%s.U%d" % (c["id"], n)] = dict(clip=c["id"], words=cu)
                    cu = []
            cu.append(x)
        if cu:
            n += 1
            units["%s.U%d" % (c["id"], n)] = dict(clip=c["id"], words=cu)
        counts[c["id"]] = n
    _dump(w, "units.json", units)
    return counts


def _unit_key(k):
    c, u = k.split(".U")
    return (c, int(u))


def units_text(w, clip=None, offset=0, limit=400):
    """Tekst jednostek dla modelu: 'C03.U12 [TC zrodla] (4,2 s) [mowca] tekst'. Stronicowanie offset/limit."""
    meta = _load(w, "clips.json")
    cl = {c["id"]: c for c in meta["clips"]}
    units = _load(w, "units.json")
    keys = sorted(units, key=_unit_key)
    if clip:
        keys = [k for k in keys if k.startswith(clip + ".")]
    out, last = [], None
    for k in keys[offset:offset + limit]:
        u = units[k]
        c = cl[u["clip"]]
        if u["clip"] != last:
            out.append("## %s %s" % (c["id"], c["name"]))
            last = u["clip"]
        ws = u["words"]
        tc = f2tc(tc2f(c["start_tc"], c["fps"]) + ws[0]["s"], c["fps"])
        out.append("%s [%s] (%s) [%s] %s" % (k, tc, fmt_s((ws[-1]["e"] - ws[0]["s"]) / c["fps"]), ws[0]["sp"],
                                            " ".join(x["t"] for x in ws)))
    rest = max(0, len(keys) - offset - limit)
    if rest:
        out.append("... jeszcze %d jednostek: units_text(W, offset=%d)" % (rest, offset + limit))
    return "\n".join(out)


# ---------------------------------------------------------------- plan
def _find(ws, phrase, last=False):
    toks = phrase.split()
    rng = range(len(ws) - len(toks), -1, -1) if last else range(len(ws) - len(toks) + 1)
    for cmp in (lambda a, b: a == b, lambda a, b: _norm(a) == _norm(b)):
        for k in rng:
            if all(cmp(ws[k + j]["t"], toks[j]) for j in range(len(toks))):
                return k, len(toks)
    return None


def resolve_plan(w, plan, pre_s=0.3, post_s=0.4):
    """plan = {"sections":[{"title":"Otwarcie","items":[{"from":"C03.U12","to":"C03.U14",
               "start_at":"fraza", "end_at":"fraza"}]}]}
    start_at: pierwsze slowa, od ktorych zaczyna sie cytat (w jednostce 'from'); end_at: ostatnie slowa (w 'to').
    Zwraca (sekcje z segmentami w klatkach zrodla, bledy). Zapasy nie wchodza na sasiednie slowa."""
    meta = _load(w, "clips.json")
    cl = {c["id"]: c for c in meta["clips"]}
    units = _load(w, "units.json")
    errors, sections = [], []
    for si, sec in enumerate(plan.get("sections") or [], 1):
        segs = []
        for ii, it in enumerate(sec.get("items") or [], 1):
            tag = "sekcja %d, pozycja %d" % (si, ii)
            a, b = it.get("from"), it.get("to") or it.get("from")
            if a not in units or b not in units:
                errors.append("%s: nie ma jednostki %s" % (tag, a if a not in units else b))
                continue
            if units[a]["clip"] != units[b]["clip"] or _unit_key(b) < _unit_key(a):
                errors.append("%s: %s..%s musi byc z jednego klipu i w kolejnosci" % (tag, a, b))
                continue
            cid = units[a]["clip"]
            keys = [k for k in sorted(units, key=_unit_key) if units[k]["clip"] == cid]
            allw = [x for k in keys for x in units[k]["words"]]
            sel = [x for k in keys[keys.index(a):keys.index(b) + 1] for x in units[k]["words"]]
            if it.get("start_at"):
                h = _find(sel, it["start_at"])
                if not h:
                    errors.append("%s: nie znaleziono start_at '%s' w %s" % (tag, it["start_at"], a))
                    continue
                sel = sel[h[0]:]
            if it.get("end_at"):
                h = _find(sel, it["end_at"], last=True)
                if not h:
                    errors.append("%s: nie znaleziono end_at '%s' w %s" % (tag, it["end_at"], b))
                    continue
                sel = sel[:h[0] + h[1]]
            if not sel:
                errors.append("%s: pusty cytat" % tag)
                continue
            c = cl[cid]
            fps = c["fps"]
            i0, i1 = allw.index(sel[0]), allw.index(sel[-1])
            prev_e = allw[i0 - 1]["e"] if i0 > 0 else 0
            next_s = allw[i1 + 1]["s"] if i1 + 1 < len(allw) else (c["frames"] or sel[-1]["e"] + 10 ** 6)
            lo = c["mark_in"] if c.get("mark_in") is not None else 0
            hi = (c["mark_out"] + 1) if c.get("mark_out") is not None else (c["frames"] or 10 ** 9)
            s = max(lo, min(sel[0]["s"], max(prev_e, sel[0]["s"] - int(round(pre_s * fps)))))
            e = min(hi, max(sel[-1]["e"], min(next_s, sel[-1]["e"] + int(round(post_s * fps)))))
            segs.append(dict(clip=cid, uid=c["uid"], name=c["name"], fps=fps, s=s, e=e, ws=sel[0]["s"], we=sel[-1]["e"], i0=i0, i1=i1,
                             sp=sel[0]["sp"], text=" ".join(x["t"] for x in sel),
                             tc=f2tc(tc2f(c["start_tc"], fps) + sel[0]["s"], fps)))
        # kolejne fragmenty tego samego klipu bez slow pomiedzy (albo nachodzace) -> jeden ciagly segment:
        # zostaje naturalna pauza i nie ma podwojnego dzwieku
        merged = []
        for g in segs:
            m = merged[-1] if merged else None
            if m and m["uid"] == g["uid"] and m["i0"] <= g["i0"] <= m["i1"] + 1:
                if g["i1"] > m["i1"]:
                    m["e"], m["we"], m["i1"], m["text"] = g["e"], g["we"], g["i1"], m["text"] + " " + g["text"]
            else:
                merged.append(g)
        sections.append(dict(title=sec.get("title") or "Sekcja %d" % si, segs=merged))
    return sections, errors


def preview(w, plan, pre_s=0.3, post_s=0.4, gap_s=0.0):
    """Tekst narracji do akceptacji + czasy liczone z klatek (model ich nie liczy). Zwraca dict(text, total_s, errors)."""
    sections, errors = resolve_plan(w, plan, pre_s, post_s)
    if errors:
        return dict(errors=errors)
    lines, total, n = [], 0.0, 0
    for i, sec in enumerate(sections):
        st = sum((g["e"] - g["s"]) / g["fps"] for g in sec["segs"])
        lines.append("### %s (%s)" % (sec["title"], fmt_s(st)))
        for g in sec["segs"]:
            n += 1
            lines.append("%d. [%s · %s %s] (%s) „%s”" % (n, g["sp"], g["clip"], g["tc"],
                                                       fmt_s((g["e"] - g["s"]) / g["fps"]), g["text"]))
        total += st + (gap_s if i < len(sections) - 1 else 0)
    lines.append("")
    lines.append("Razem: %s (%s), %d %s, %d %s" % (fmt_mmss(total), fmt_s(total), n, plural(n, "wypowiedź", "wypowiedzi", "wypowiedzi"),
                                                 len(sections), plural(len(sections), "sekcja", "sekcje", "sekcji")))
    _dump(w, "plan.json", plan)
    return dict(text="\n".join(lines), total_s=round(total, 2), items=n, errors=[])


# ---------------------------------------------------------------- timeline
def timeline_exists(project, name):
    for i in range(1, project.GetTimelineCount() + 1):
        if project.GetTimelineByIndex(i).GetName() == name:
            return True
    return False


def build_timeline(project, w, name, plan=None, pre_s=0.3, post_s=0.4, gap_s=0.0, markers=True):
    """Buduje NOWY timeline z planu jednostek (domyslnie zapisany plan.json)."""
    plan = plan or _load(w, "plan.json")
    sections, errors = resolve_plan(w, plan, pre_s, post_s)
    if errors:
        return dict(ok=False, errors=errors)
    r = _place_sections(project, name, sections, gap_s, markers)
    if r.get("ok") is not None and w:
        log = _load(w, "builds.json") if os.path.exists(os.path.join(w, "builds.json")) else []
        log.append(dict(name=name, plan=plan, at=time.strftime("%Y-%m-%d %H:%M")))
        _dump(w, "builds.json", log)
    return r


def _place_sections(project, name, sections, gap_s=0.0, markers=True):
    """Sklada NOWY timeline z rozwiazanych sekcji. Nigdy nie zmienia istniejacych timeline'ow.
    Zwraca raport: liczba klipow, dlugosc, kontrola dziur i nakladek."""
    if timeline_exists(project, name):
        return dict(ok=False, errors=["timeline '%s' juz istnieje - podaj inna nazwe" % name])
    mp = project.GetMediaPool()
    folder_before = mp.GetCurrentFolder()
    mp.SetCurrentFolder(mp.GetRootFolder())  # bez tego CreateEmptyTimeline potrafi zwrocic None
    tl = mp.CreateEmptyTimeline(name)
    if not tl:
        mp.SetCurrentFolder(folder_before)
        return dict(ok=False, errors=["nie udalo sie utworzyc timeline'u '%s'" % name])
    project.SetCurrentTimeline(tl)
    tfps = exact_fps(tl.GetSetting("timelineFrameRate") or project.GetSetting("timelineFrameRate") or 25)
    gap_f = int(round(gap_s * tfps))
    rec = tl.GetStartFrame()
    placed, warn = [], []
    for si, sec in enumerate(sections):
        if si and gap_f:
            rec += gap_f
        sec_start = rec
        for g in sec["segs"]:
            item = clip_by_uid(project, g["uid"])
            info = dict(mediaPoolItem=item, startFrame=g["s"], endFrame=g["e"] if END_EXCLUSIVE else g["e"] - 1,
                        recordFrame=rec)
            got = mp.AppendToTimeline([info]) or []
            if not got:
                warn.append("nie dodano %s %s" % (g["clip"], g["tc"]))
                continue
            st = min(int(round(x.GetStart())) for x in got)
            en = max(int(round(x.GetEnd())) for x in got)
            exp = int(round((g["e"] - g["s"]) * tfps / g["fps"]))
            if abs((en - st) - exp) > 1:
                warn.append("%s %s: dlugosc %d kl., oczekiwano %d" % (g["clip"], g["tc"], en - st, exp))
            if st != rec:
                warn.append("%s %s: start %d zamiast %d" % (g["clip"], g["tc"], st, rec))
            placed.append(dict(st=st, en=en, sec=si))
            rec = en  # nastepny od faktycznego konca (unika 1-klatkowych dziur przy roznym FPS)
        if markers and sec["segs"]:
            try:
                tl.AddMarker(sec_start - tl.GetStartFrame(), "Blue", sec["title"], "", 1)
            except Exception:
                pass
    mp.SetCurrentFolder(folder_before)
    # kontrola: dziury i nakladki w obrebie sekcji
    for a, b in zip(placed, placed[1:]):
        d = b["st"] - a["en"]
        if d < 0:
            warn.append("nakladka %d kl. przy %s" % (-d, f2tc(b["st"], tfps)))
        elif d > 0 and a["sec"] == b["sec"]:
            warn.append("dziura %d kl. przy %s" % (d, f2tc(a["en"], tfps)))
    total = (placed[-1]["en"] - placed[0]["st"]) / tfps if placed else 0
    return dict(ok=not [x for x in warn if x.startswith(("nie dodano", "nakladka"))], timeline=name, clips=len(placed),
                duration=fmt_mmss(total), duration_s=round(total, 2), warnings=warn)


# ================================================================ KATALOG
def _clip_info_all(project):
    """Opis wszystkich klipow z dzwiekiem w projekcie (do odnajdywania klipow po nazwie w zwrotce)."""
    out = []
    for c in _all_clips(project.GetMediaPool()):
        if not _has_audio(c):
            continue
        marks = {}
        try:
            mi = c.GetMarkInOut() or {}
            marks = mi.get("audio") or mi.get("video") or {}
        except Exception:
            pass
        out.append(dict(uid=c.GetUniqueId(), name=c.GetName(), fps=exact_fps(c.GetClipProperty("FPS") or 25),
                        start_tc=c.GetClipProperty("Start TC") or "00:00:00:00", frames=int(c.GetClipProperty("Frames") or 0),
                        path=c.GetClipProperty("File Path") or "", mark_in=marks.get("in"), mark_out=marks.get("out")))
    return out


def _words(project, info):
    """Slowa klipu w klatkach zrodla (wzgledem poczatku klipu), przyciete do In/Out."""
    tr = _transcription(project, info)
    if not tr:
        return []
    fps = info["fps"]
    c0 = tc2f(info["start_tc"], fps)
    words = []
    for seg in tr.get("segments") or []:
        first = True
        for wd in seg.get("words") or []:
            t = (wd.get("text") or "").strip()
            if not t or t == "(...)" or not re.search(r"\w", t):
                first = True
                continue
            s, e = tc2f(wd["start"], fps) - c0, tc2f(wd["end"], fps) - c0
            words.append(dict(t=t, s=s, e=max(e, s + 1), sp=seg.get("speaker") or "S1", first=first))
            first = False
    fix_stretched(words, fps)
    lo = info["mark_in"] if info.get("mark_in") is not None else 0
    hi = info["mark_out"] if info.get("mark_out") is not None else 10 ** 9
    return [x for x in words if x["s"] >= lo and x["e"] <= hi + 1]


def _src_tc(info, frame):
    return f2tc(tc2f(info["start_tc"], info["fps"]) + frame, info["fps"])


def default_docx_path(project):
    base = os.path.join(os.path.expanduser("~"), "Desktop", "Katalog_" + safe_name(project.GetName()))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "%s_katalog_%s.docx" % (safe_name(project.GetName()), time.strftime("%Y%m%d-%H%M")))


def apply_catalog(project, w, cat, docx_path=None, write_metadata=True, write_markers=True, intellisearch=False):
    """cat = {"title": "...", "subtitle": "...",
              "people": {"C01": {"name": "Anna Nowak", "role": "organizatorka", "summary": "...", "topics": ["frekwencja"]}},
              "overview": [{"heading": "...", "paragraphs": ["..."], "bullets": ["..."]}],
              "quotes": [{"id": "Q001", "topic": "Frekwencja", "from": "C01.U4", "to": "C01.U6",
                          "start_at": "...", "end_at": "...", "broll": "tlum, sala"}]}
    Zapisuje metadane klipow, markery z ID na klipach zrodlowych i dokument DOCX. Zwraca raport."""
    meta = _load(w, "clips.json")
    cl = {c["id"]: c for c in meta["clips"]}
    units = _load(w, "units.json")
    people = cat.get("people") or {}
    errors, quotes = [], []
    for q in cat.get("quotes") or []:
        secs, err = resolve_plan(w, {"sections": [{"items": [q]}]}, pre_s=0, post_s=0)
        if err:
            errors += ["%s: %s" % (q.get("id"), e) for e in err]
            continue
        g = secs[0]["segs"][0]
        quotes.append(dict(q, seg=g))
    ids = [q["id"] for q in quotes]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errors.append("powtorzone ID: " + ", ".join(dup))
    if errors:
        return dict(ok=False, errors=errors)
    _dump(w, "catalog.json", cat)
    rep = dict(ok=True, quotes=len(quotes), markers=0, metadata_set=[], metadata_kept=[], warnings=[])

    # metadane klipow: Description tylko gdy puste, Keywords dopisywane (nie usuwamy cudzych)
    if write_metadata:
        for cid, c in cl.items():
            p = people.get(cid)
            if not p:
                continue
            item = clip_by_uid(project, c["uid"])
            md = item.GetMetadata() or {}
            topics = sorted({q.get("topic") for q in quotes if q["seg"]["clip"] == cid and q.get("topic")} | set(p.get("topics") or []))
            kw_old = [k.strip() for k in (md.get("Keywords") or "").split(",") if k.strip()]
            kw_new = ["osoba:" + p["name"]] + ["temat:" + t for t in topics]
            kw = kw_old + [k for k in kw_new if k not in kw_old]
            upd = {"Keywords": ",".join(kw)}
            desc = " – ".join(x for x in (p.get("name"), p.get("role")) if x)
            if p.get("summary"):
                desc += ". " + p["summary"]
            if not (md.get("Description") or "").strip():
                upd["Description"] = desc
                rep["metadata_set"].append(c["name"])
            else:
                rep["metadata_kept"].append(c["name"])
            if not item.SetMetadata(upd):
                rep["warnings"].append("nie zapisano metadanych: " + c["name"])

    # markery z ID na klipach zrodlowych (poprzednie markery katalogu sa usuwane, cudze zostaja)
    if write_markers:
        done = set()
        for q in quotes:
            g = q["seg"]
            item = clip_by_uid(project, g["uid"])
            if g["uid"] not in done:
                for fr, mk in (item.GetMarkers() or {}).items():
                    if str(mk.get("customData") or "").startswith(MARKER_TAG):
                        item.DeleteMarkerAtFrame(fr)
                done.add(g["uid"])
            data = json.dumps(dict(id=q["id"], s=g["ws"], e=g["we"]), separators=(",", ":"))
            name = ("%s %s" % (q["id"], q.get("topic") or "")).strip()
            if item.AddMarker(g["ws"], MARKER_COLOR, name[:60], g["text"][:500], max(1, g["we"] - g["ws"]),
                              MARKER_TAG + ":" + data):
                rep["markers"] += 1
            else:
                rep["warnings"].append("%s: nie dodano markera (zajeta klatka %s?)" % (q["id"], g["tc"]))

    # IntelliSearch z twarzami na binie z wywiadami (wyszukiwarka w Resolve + kolumna People)
    if intellisearch:
        mp = project.GetMediaPool()
        b = meta.get("bin")
        folder = mp.GetCurrentFolder() if b in (None, "(biezacy)") else _folder_by_path(mp, [] if b == "(Master)" else b.split("/"))
        try:
            rep["intellisearch"] = bool(folder and folder.AnalyzeForIntellisearch(True, False))
        except Exception as e:
            rep["intellisearch"] = False
            rep["warnings"].append("IntelliSearch: %s" % e)
        if not rep["intellisearch"]:
            rep["warnings"].append("IntelliSearch nie wystartowal (brak pakietu 'AI IntelliSearch - Faster' w Extras?)")

    # dokument
    rep["docx"] = write_catalog_docx(docx_path or default_docx_path(project), cat, quotes, cl, units, people)
    return rep


# ---------------------------------------------------------------- DOCX: generator bez zaleznosci
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _x(t):
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(t))
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _runs(text, bold=False, size=None, color=None):
    rpr = ""
    if bold or size or color:
        rpr = "<w:rPr>%s%s%s</w:rPr>" % ("<w:b/>" if bold else "", '<w:sz w:val="%d"/>' % size if size else "",
                                        '<w:color w:val="%s"/>' % color if color else "")
    parts = str(text).split("\n")
    out = []
    for i, p in enumerate(parts):
        if i:
            out.append("<w:r>%s<w:br/></w:r>" % rpr)
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, _x(p)))
    return "".join(out)


def _p(text, style=None, bold=False, size=None, color=None, indent=None, after=None):
    ppr = ""
    if style or indent or after is not None:
        ppr = "<w:pPr>%s%s%s</w:pPr>" % ('<w:pStyle w:val="%s"/>' % style if style else "",
                                        '<w:spacing w:after="%d"/>' % after if after is not None else "",
                                        '<w:ind w:left="%d" w:hanging="240"/>' % indent if indent else "")
    return "<w:p>%s%s</w:p>" % (ppr, _runs(text, bold, size, color))


def _table(headers, rows, widths, fill_cols=(), header_fill="D9D9D9", fill="FFF2CC"):
    grid = "".join('<w:gridCol w:w="%d"/>' % x for x in widths)
    b = '<w:%s w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
    borders = "<w:tblBorders>%s</w:tblBorders>" % "".join(b % s for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    out = ['<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/>%s<w:tblLayout w:type="fixed"/>'
           '<w:tblCellMar><w:left w:w="70" w:type="dxa"/><w:right w:w="70" w:type="dxa"/></w:tblCellMar>'
           '</w:tblPr><w:tblGrid>%s</w:tblGrid>' % (sum(widths), borders, grid)]

    def cell(text, wd, shade=None, bold=False):
        sh = '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shade if shade else ""
        paras = "".join(_p(t, bold=bold, after=0) for t in (str(text).split("\n\n") or [""]))
        return '<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s</w:tcPr>%s</w:tc>' % (wd, sh, paras or "<w:p/>")

    out.append('<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>%s</w:tr>'
               % "".join(cell(h, wd, header_fill, True) for h, wd in zip(headers, widths)))
    for r in rows:
        out.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>%s</w:tr>'
                   % "".join(cell(v, wd, fill if i in fill_cols else None) for i, (v, wd) in enumerate(zip(r, widths))))
    out.append("</w:tbl>")
    return "".join(out)


_STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles %s>'
           '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/>'
           '<w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="pl-PL"/></w:rPr></w:rPrDefault>'
           '<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
           '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
           '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>'
           '<w:pPr><w:spacing w:after="120"/></w:pPr><w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
           '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>'
           '<w:pPr><w:keepNext/><w:spacing w:before="320" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>'
           '<w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
           '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>'
           '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr>'
           '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style></w:styles>') % _W


def write_docx(path, blocks, title="Dokument"):
    """blocks: lista ("title"|"h1"|"h2"|"p"|"bullet"|"note", tekst) albo ("table", headers, rows, widths, fill_cols).
    A4 poziomo. Zwraca sciezke."""
    import zipfile
    body = []
    for b in blocks:
        k = b[0]
        if k == "title":
            body.append(_p(b[1], "Title"))
        elif k == "h1":
            body.append(_p(b[1], "Heading1"))
        elif k == "h2":
            body.append(_p(b[1], "Heading2"))
        elif k == "bullet":
            body.append(_p("•\t" + b[1], indent=360))
        elif k == "note":
            body.append(_p(b[1], color="595959"))
        elif k == "table":
            body.append(_table(b[1], b[2], b[3], b[4] if len(b) > 4 else ()))
            body.append(_p("", after=0))
        else:
            body.append(_p(b[1]))
    sect = ('<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
            '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/></w:sectPr>')
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document %s><w:body>%s%s</w:body></w:document>'
           % (_W, "".join(body), sect))
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '</Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
             '</Relationships>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>%s</dc:title><dc:creator>fzp-katalog-wypowiedzi</dc:creator>'
            '<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created></cp:coreProperties>'
            % (_x(title), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", drels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", _STYLES)
        z.writestr("docProps/core.xml", core)
    return path


# kolumny tabel (zwrotka szuka ich po naglowkach, wiec kolejnosc moze sie zmienic)
COL_ORDER, COL_ID, COL_WHO, COL_CLIP, COL_DUR, COL_TEXT, COL_BROLL, COL_NOTES = (
    "Kol.", "ID", "Kto", "Klip / TC", "Czas", "Cytat", "Przebitki do szukania", "Uwagi")


def write_catalog_docx(path, cat, quotes, cl, units, people):
    who = lambda cid: (people.get(cid) or {}).get("name") or "osoba z %s" % cid
    blocks = [("title", cat.get("title") or "Katalog wypowiedzi")]
    if cat.get("subtitle"):
        blocks.append(("note", cat["subtitle"]))
    blocks.append(("h1", "Jak pracować z tym dokumentem"))
    for t in ("W kolumnie „%s” (żółtej) wpisz numery wypowiedzi w kolejności, w jakiej mają pójść w filmie: 1, 2, 3… "
              "Możesz wybierać z tabeli cytatów i z aneksu z pełnym zapisem. Żeby wstawić coś pomiędzy, użyj np. 2.5." % COL_ORDER,
              "W kolumnie „%s” dopisz, co zmienić, np. „tylko pierwsze zdanie”, „bez końcówki”, „tu muzyka”. "
              "Możesz też skreślić albo usunąć słowa z cytatu, żeby go skrócić." % COL_NOTES,
              "Nie usuwaj kolumn „%s” i „%s” – po nich montażysta odtworzy wybór w programie." % (COL_ID, COL_CLIP)):
        blocks.append(("bullet", t))
    for sec in cat.get("overview") or []:
        blocks.append(("h1", sec.get("heading") or ""))
        for t in sec.get("paragraphs") or []:
            blocks.append(("p", t))
        for t in sec.get("bullets") or []:
            blocks.append(("bullet", t))
    # cytaty pogrupowane po tematach (w kolejnosci pierwszego wystapienia)
    blocks.append(("h1", "Wybrane cytaty"))
    topics = []
    for q in quotes:
        if q.get("topic") not in topics:
            topics.append(q.get("topic"))
    widths = [700, 760, 1700, 2150, 700, 6000, 1700, 1690]
    for t in topics:
        rows = []
        for q in [x for x in quotes if x.get("topic") == t]:
            g = q["seg"]
            c = cl[g["clip"]]
            rows.append(["", q["id"], who(g["clip"]), "%s\n%s–%s" % (c["name"], _src_tc(c, g["ws"]), _src_tc(c, g["we"])),
                         fmt_s((g["we"] - g["ws"]) / g["fps"]), g["text"], q.get("broll") or "", ""])
        blocks.append(("h2", t or "Bez tematu"))
        blocks.append(("table", [COL_ORDER, COL_ID, COL_WHO, COL_CLIP, COL_DUR, COL_TEXT, COL_BROLL, COL_NOTES], rows, widths, (0,)))
    # aneks: pelny zapis per klip
    blocks.append(("h1", "Aneks – pełny zapis wypowiedzi"))
    blocks.append(("note", "Każde zdanie ma ID i można je wybrać tak samo jak cytaty powyżej."))
    widths2 = [700, 900, 2150, 700, 9450, 1500]
    for cid in sorted(cl):
        keys = sorted([k for k in units if units[k]["clip"] == cid], key=_unit_key)
        if not keys:
            continue
        c = cl[cid]
        rows = []
        for k in keys:
            ws = units[k]["words"]
            rows.append(["", k, "%s\n%s–%s" % (c["name"], _src_tc(c, ws[0]["s"]), _src_tc(c, ws[-1]["e"])),
                         fmt_s((ws[-1]["e"] - ws[0]["s"]) / c["fps"]), " ".join(x["t"] for x in ws), ""])
        blocks.append(("h2", "%s – %s" % (who(cid), c["name"])))
        blocks.append(("table", [COL_ORDER, COL_ID, COL_CLIP, COL_DUR, COL_TEXT, COL_NOTES], rows, widths2, (0,)))
    return write_docx(path, blocks, cat.get("title") or "Katalog wypowiedzi")


# ---------------------------------------------------------------- DOCX: odczyt odeslanego dokumentu
def read_docx_tables(path):
    """Wszystkie tabele z DOCX jako listy wierszy (komorka = tekst, akapity rozdzielone '\\n').
    Tekst skreslony (w:strike, w:dstrike) i usuniety w sledzeniu zmian (w:del) jest pomijany."""
    import zipfile
    import xml.etree.ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))

    def run_text(r):
        rpr = r.find(ns + "rPr")
        if rpr is not None:
            for tag in ("strike", "dstrike"):
                el = rpr.find(ns + tag)
                if el is not None and el.get(ns + "val") not in ("0", "false"):
                    return ""
        out = []
        for ch in r:
            if ch.tag == ns + "t":
                out.append(ch.text or "")
            elif ch.tag in (ns + "br", ns + "cr"):
                out.append("\n")
            elif ch.tag == ns + "tab":
                out.append(" ")
        return "".join(out)

    def para_text(p):
        out = []
        for el in p.iter():
            if el.tag == ns + "r":
                # pomijamy runy wewnatrz usuniec sledzenia zmian
                out.append(run_text(el))
        return "".join(out)

    def strip_deleted(el):
        for parent in el.iter():
            for ch in list(parent):
                if ch.tag == ns + "del":
                    parent.remove(ch)

    strip_deleted(root)
    tables = []
    for tbl in root.iter(ns + "tbl"):
        rows = []
        for tr in tbl.findall(ns + "tr"):
            cells = []
            for tc in tr.findall(ns + "tc"):
                cells.append("\n".join(para_text(p) for p in tc.findall(ns + "p")).strip())
            rows.append(cells)
        tables.append(rows)
    return tables


_TC_RANGE = re.compile(r"(\d\d:\d\d:\d\d[:;]\d\d)\s*[–\-—]\s*(\d\d:\d\d:\d\d[:;]\d\d)")


def selection_from_docx(path):
    """Czyta odeslany dokument: wiersze z wpisana kolejnoscia w kolumnie 'Kol.' z tabel cytatow i aneksu.
    Zwraca dict(items=[...] w kolejnosci, errors=[...], warnings=[...])."""
    items, errors, warnings = [], [], []
    for rows in read_docx_tables(path):
        if not rows:
            continue
        hdr = [h.strip() for h in rows[0]]
        if COL_ORDER not in hdr or COL_ID not in hdr:
            continue
        ix = {h: i for i, h in enumerate(hdr)}
        if COL_CLIP not in ix:
            errors.append("tabela bez kolumny '%s' – nie da sie odtworzyc zakresow" % COL_CLIP)
            continue
        text_col = ix.get(COL_TEXT, ix.get("Tekst"))
        for r in rows[1:]:
            get = lambda k: r[ix[k]].strip() if k in ix and ix[k] < len(r) else ""
            order = get(COL_ORDER)
            if not order:
                continue
            m = re.match(r"^\s*(\d+(?:[.,]\d+)?)", order)
            if not m:
                warnings.append("%s: nieczytelna kolejnosc '%s' – pominiete" % (get(COL_ID) or "?", order))
                continue
            clip_cell = get(COL_CLIP)
            tm = _TC_RANGE.search(clip_cell)
            if not tm:
                errors.append("%s: brak zakresu TC w kolumnie '%s'" % (get(COL_ID) or "?", COL_CLIP))
                continue
            clip = clip_cell[:tm.start()].strip().strip("\n").strip()
            items.append(dict(order=float(m.group(1).replace(",", ".")), id=get(COL_ID), who=get(COL_WHO), clip=clip,
                              tc_in=tm.group(1), tc_out=tm.group(2),
                              text=r[text_col].strip() if text_col is not None and text_col < len(r) else "",
                              notes=get(COL_NOTES)))
    seen = {}
    for it in items:
        seen.setdefault(it["order"], []).append(it["id"])
    for o, l in sorted(seen.items()):
        if len(l) > 1:
            warnings.append("ten sam numer %g przy: %s – zostawiam kolejnosc z dokumentu" % (o, ", ".join(l)))
    items.sort(key=lambda x: x["order"])  # sort stabilny: rowne numery zachowuja kolejnosc z dokumentu
    if not items and not errors:
        errors.append("nie znaleziono zadnego wpisu w kolumnie '%s'" % COL_ORDER)
    return dict(items=items, errors=errors, warnings=warnings)


# ---------------------------------------------------------------- zwrotka: zakresy klip + TC -> timeline
def _resolve_items(project, items, pre_s=0.3, post_s=0.4):
    """items: [{"section": "...", "clip": "nazwa klipu", "tc_in": "...", "tc_out": "...", "start_at": "...", "end_at": "..."}]
    Odnajduje klip po nazwie (przy kilku o tej samej nazwie - ten, ktorego In/Out obejmuje zakres) i slowa w zakresie."""
    infos = _clip_info_all(project)
    sections, errors = [], []
    cache = {}
    for n, it in enumerate(items, 1):
        tag = "pozycja %d (%s)" % (n, it.get("id") or it.get("clip"))
        cands = [c for c in infos if c["name"] == it.get("clip")]
        if not cands:
            errors.append("%s: nie ma klipu '%s' w projekcie" % (tag, it.get("clip")))
            continue

        def inside(c):
            a = tc2f(it["tc_in"], c["fps"]) - tc2f(c["start_tc"], c["fps"])
            lo = c["mark_in"] if c.get("mark_in") is not None else 0
            hi = c["mark_out"] if c.get("mark_out") is not None else 10 ** 9
            return lo <= a <= hi

        c = ([x for x in cands if inside(x)] or cands)[0]
        if c["uid"] not in cache:
            cache[c["uid"]] = _words(project, c)
        allw = cache[c["uid"]]
        fps = c["fps"]
        a = tc2f(it["tc_in"], fps) - tc2f(c["start_tc"], fps)
        b = tc2f(it["tc_out"], fps) - tc2f(c["start_tc"], fps)
        sel = [x for x in allw if x["s"] >= a - 2 and x["e"] <= b + 2]
        if not sel:
            errors.append("%s: brak slow w zakresie %s–%s (brak transkrypcji?)" % (tag, it["tc_in"], it["tc_out"]))
            continue
        if it.get("start_at"):
            h = _find(sel, it["start_at"])
            if not h:
                errors.append("%s: nie znaleziono start_at '%s'" % (tag, it["start_at"]))
                continue
            sel = sel[h[0]:]
        if it.get("end_at"):
            h = _find(sel, it["end_at"], last=True)
            if not h:
                errors.append("%s: nie znaleziono end_at '%s'" % (tag, it["end_at"]))
                continue
            sel = sel[:h[0] + h[1]]
        i0, i1 = allw.index(sel[0]), allw.index(sel[-1])
        prev_e = allw[i0 - 1]["e"] if i0 > 0 else 0
        next_s = allw[i1 + 1]["s"] if i1 + 1 < len(allw) else (c["frames"] or sel[-1]["e"] + 10 ** 6)
        lo = c["mark_in"] if c.get("mark_in") is not None else 0
        hi = (c["mark_out"] + 1) if c.get("mark_out") is not None else (c["frames"] or 10 ** 9)
        s = max(lo, min(sel[0]["s"], max(prev_e, sel[0]["s"] - int(round(pre_s * fps)))))
        e = min(hi, max(sel[-1]["e"], min(next_s, sel[-1]["e"] + int(round(post_s * fps)))))
        g = dict(clip=it.get("id") or c["name"], uid=c["uid"], name=c["name"], fps=fps, s=s, e=e, ws=sel[0]["s"],
                 we=sel[-1]["e"], i0=i0, i1=i1, sp=it.get("who") or sel[0]["sp"], text=" ".join(x["t"] for x in sel),
                 tc=_src_tc(c, sel[0]["s"]))
        title = it.get("section") or "Wybór"
        if not sections or sections[-1]["title"] != title:
            sections.append(dict(title=title, segs=[]))
        m = sections[-1]["segs"][-1] if sections[-1]["segs"] else None
        if m and m["uid"] == g["uid"] and m["i0"] <= g["i0"] <= m["i1"] + 1:
            if g["i1"] > m["i1"]:
                m["e"], m["we"], m["i1"], m["text"] = g["e"], g["we"], g["i1"], m["text"] + " " + g["text"]
        else:
            sections[-1]["segs"].append(g)
    return sections, errors


def preview_items(project, items, pre_s=0.3, post_s=0.4, gap_s=0.0):
    """Podglad wyboru z dokumentu z czasami (jak preview w narracji)."""
    sections, errors = _resolve_items(project, items, pre_s, post_s)
    if errors:
        return dict(errors=errors)
    lines, total, n = [], 0.0, 0
    for i, sec in enumerate(sections):
        st = sum((g["e"] - g["s"]) / g["fps"] for g in sec["segs"])
        lines.append("### %s (%s)" % (sec["title"], fmt_s(st)))
        for g in sec["segs"]:
            n += 1
            lines.append("%d. [%s · %s %s] (%s) „%s”" % (n, g["sp"], g["clip"], g["tc"], fmt_s((g["e"] - g["s"]) / g["fps"]), g["text"]))
        total += st + (gap_s if i < len(sections) - 1 else 0)
    lines.append("")
    lines.append("Razem: %s (%s), %d %s, %d %s" % (fmt_mmss(total), fmt_s(total), n, plural(n, "wypowiedź", "wypowiedzi", "wypowiedzi"),
                                                 len(sections), plural(len(sections), "sekcja", "sekcje", "sekcji")))
    return dict(text="\n".join(lines), total_s=round(total, 2), items=n, errors=[])


def build_from_items(project, name, items, pre_s=0.3, post_s=0.4, gap_s=0.0, markers=True):
    """Buduje NOWY timeline z wyboru odczytanego z dokumentu (po akceptacji)."""
    sections, errors = _resolve_items(project, items, pre_s, post_s)
    if errors:
        return dict(ok=False, errors=errors)
    return _place_sections(project, name, sections, gap_s, markers)

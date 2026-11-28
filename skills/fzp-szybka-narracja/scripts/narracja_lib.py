# narracja_lib - biblioteka skilla "fzp-szybka-narracja". Nie edytuj recznie.
# Copyright (c) 2026 Marcin / Filmowanie z Profitem (filmowaniezprofitem.pl)
# Licencja: MIT + Commons Clause (zob. LICENSE w repozytorium fzp_mcp_skills)
import json, os, re, sys, time

LIB_VERSION = "1.1"
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
    base = os.path.join(os.path.expanduser("~"), ".fzp-szybka-narracja", "work")
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


_DATE_FMTS = ("%a %b %d %H:%M:%S %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
              "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%Y:%m:%d %H:%M:%S")


def _clip_date(c):
    """Data nagrania pliku (Date Created z Media Poola) jako czas epoki albo None."""
    for key in ("Date Created", "Date Recorded", "Shot Date"):
        v = (c.GetClipProperty(key) or "").strip()
        if not v:
            continue
        for f in _DATE_FMTS:
            try:
                return time.mktime(time.strptime(v, f))
            except Exception:
                pass
    return None


def _clip_info(i, c, mark_in=None, mark_out=None, **extra):
    fps = exact_fps(c.GetClipProperty("FPS") or 25)
    tr = c.GetTranscription() or {}
    d = dict(id="C%02d" % i, uid=c.GetUniqueId(), name=c.GetName(), fps=fps,
             start_tc=c.GetClipProperty("Start TC") or "00:00:00:00",
             frames=int(c.GetClipProperty("Frames") or 0), path=c.GetClipProperty("File Path") or "",
             duration=c.GetClipProperty("Duration") or "", mark_in=mark_in, mark_out=mark_out,
             date=c.GetClipProperty("Date Created") or "",
             transcribed=bool(tr.get("segments")), transcription_lang=tr.get("language"))
    d.update(extra)
    return d


def inventory(project, w, bin_path=None, recursive=False, order="date"):
    """Klipy z dzwiekiem we wskazanym binie (sciezka 'A/B' albo biezacy folder). Zapisuje clips.json, zwraca liste.
    order: "date" (data nagrania pliku, potem Start TC), "tc" (Start TC) albo "name". Kolejnosc wyznacza numery C01, C02..."""
    mp = project.GetMediaPool()
    folder = mp.GetCurrentFolder() if not bin_path else _folder_by_path(mp, [] if bin_path == "(Master)" else bin_path.split("/"))
    if folder is None:
        raise RuntimeError("Nie ma binu: %s" % bin_path)
    src = [x for _, x in _walk(folder, [], [])] if recursive else [folder]
    clips = []
    for f in src:
        clips += [c for c in (f.GetClipList() or []) if _has_audio(c)]
    def tc_key(c):
        return tc2f(c.GetClipProperty("Start TC") or "00:00:00:00", exact_fps(c.GetClipProperty("FPS") or 25))
    if order == "name":
        clips.sort(key=lambda c: c.GetName())
    elif order == "tc":
        clips.sort(key=lambda c: (tc_key(c), c.GetName()))
    else:  # data nagrania; bez daty -> na koniec, po Start TC
        clips.sort(key=lambda c: (_clip_date(c) is None, _clip_date(c) or 0, tc_key(c), c.GetName()))
    out = []
    for i, c in enumerate(clips, 1):
        marks = {}
        try:
            marks = (c.GetMarkInOut() or {}).get("audio") or (c.GetMarkInOut() or {}).get("video") or {}
        except Exception:
            pass
        out.append(_clip_info(i, c, marks.get("in"), marks.get("out")))
    _dump(w, "clips.json", dict(source="bin", bin=bin_path or "(biezacy)", order=order, clips=out,
                                tl_fps=float(project.GetSetting("timelineFrameRate") or 25)))
    return out


def list_timelines(project):
    cur = project.GetCurrentTimeline()
    return [dict(name=t.GetName(), current=bool(cur) and t.GetUniqueId() == cur.GetUniqueId())
            for t in (project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1))]


def inventory_timeline(project, w, timeline_name=None):
    """Wypowiedzi z timeline'u w kolejnosci na osi czasu (domyslnie biezacy timeline). Kazdy klip na timeline'ie
    = osobne C01, C02... z zakresem uzytym na timeline'ie. Zapisuje clips.json, zwraca liste."""
    tl = project.GetCurrentTimeline()
    if timeline_name:
        tl = next((project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1)
                   if project.GetTimelineByIndex(i).GetName() == timeline_name), None)
    if tl is None:
        raise RuntimeError("Nie ma timeline'u: %s" % timeline_name)
    tfps = exact_fps(tl.GetSetting("timelineFrameRate") or 25)
    items = []
    for kind in ("video", "audio"):  # wideo wyznacza kolejnosc; same audio tylko, gdy nie ma wideo
        for k in range(1, tl.GetTrackCount(kind) + 1):
            for it in tl.GetItemListInTrack(kind, k) or []:
                m = it.GetMediaPoolItem()
                if m and _has_audio(m):
                    items.append((it.GetStart(), k, it, m))
        if items:
            break
    items.sort(key=lambda x: (x[0], x[1]))
    out, seen = [], set()
    for start, _, it, m in items:
        key = (m.GetUniqueId(), it.GetLeftOffset(), it.GetDuration())
        if key in seen:  # ten sam fragment na kilku sciezkach
            continue
        seen.add(key)
        sfps = exact_fps(m.GetClipProperty("FPS") or 25)
        lo = int(it.GetLeftOffset())
        hi = lo + int(round(it.GetDuration() * sfps / tfps)) - 1
        out.append(_clip_info(len(out) + 1, m, lo, hi, src_off=int(it.GetSourceStartFrame()) - lo,
                              tl_tc=f2tc(start, tfps)))
    _dump(w, "clips.json", dict(source="timeline", timeline=tl.GetName(), clips=out, tl_fps=float(tfps)))
    return out


# ---------------------------------------------------------------- transkrypcja
def _transcription(project, info, lang=None):
    """Transkrypcja klipu (subclip ma wlasna, w zakresie swojego In/Out). Z lang: tylko w tym jezyku."""
    c = clip_by_uid(project, info["uid"])
    tr = c.GetTranscription() if c else None
    if not (tr and tr.get("segments")):
        return None
    if lang and tr.get("language") and tr.get("language") != lang:
        return None
    return tr


def set_transcription_language(project, lang):
    """Ustawia jezyk transkrypcji. Czesc jezykow (m.in. polski) dziala tylko z wlaczonym
    transcriptionExtendedLanguageSupport. Zwraca True, gdy ustawienie sie przyjelo."""
    if project.GetSetting("transcriptionLanguage") == lang:
        return True
    project.SetSetting("transcriptionLanguage", lang)
    if project.GetSetting("transcriptionLanguage") == lang:
        return True
    project.SetSetting("transcriptionExtendedLanguageSupport", "1")
    project.SetSetting("transcriptionLanguage", lang)
    return project.GetSetting("transcriptionLanguage") == lang


def transcribe_step(resolve, project, w, lang="pl", wait_s=50, poll_s=5):
    """Transkrybuje po kolei klipy bez transkrypcji w jezyku lang (transkrypcje w innym jezyku czysci i robi od nowa).
    Kazdy klip osobno (subclip = jego zakres). Wywoluj w petli, az zwroci status 'gotowe'. Czeka do wait_s."""
    meta = _load(w, "clips.json")
    st_path = os.path.join(w, "transcribe.json")
    st = _load(w, "transcribe.json") if os.path.exists(st_path) else dict(
        lang=lang, lang_before=project.GetSetting("transcriptionLanguage"),
        ext_before=project.GetSetting("transcriptionExtendedLanguageSupport"), started=[])
    _dump(w, "transcribe.json", st)
    if not set_transcription_language(project, lang):
        return dict(status="blad", error="Resolve nie przyjal jezyka transkrypcji '%s'" % lang)
    if resolve.GetCurrentPage() != "edit":
        st.setdefault("page_before", resolve.GetCurrentPage())
        resolve.OpenPage("edit")
    t0 = time.time()
    while True:
        js = project.GetTranscribeAudioStatus() or {}
        busy = js.get("JobStatus") in ("Initializing", "Analyzing", "Cancelling")
        if not busy:
            todo, uids = [], set()
            for c in meta["clips"]:  # ten sam klip kilka razy na timeline'ie -> jedna transkrypcja
                if c["uid"] in st["started"] or c["uid"] in uids or _transcription(project, c, lang):
                    continue
                uids.add(c["uid"])
                todo.append(c)
            if not todo:
                missing = [c["id"] for c in meta["clips"] if not _transcription(project, c, lang)]
                _dump(w, "transcribe.json", st)
                return dict(status="gotowe" if not missing else "bledy", missing=missing, error=js.get("Error"))
            c = clip_by_uid(project, todo[0]["uid"])
            if (c.GetTranscription() or {}).get("segments"):
                c.ClearTranscription()  # transkrypcja w innym jezyku
            ok = c.TranscribeAudio(True, False)
            st["started"].append(todo[0]["uid"])
            _dump(w, "transcribe.json", st)
            if not ok:
                return dict(status="blad", clip=todo[0]["id"], error="TranscribeAudio zwrocilo False")
        if time.time() - t0 >= wait_s:
            done = sum(1 for c in meta["clips"] if _transcription(project, c, lang))
            return dict(status="w toku", done=done, total=len(meta["clips"]),
                        percent=js.get("CompletionPercentage"), eta_s=js.get("EstimatedTimeRemaining"))
        time.sleep(poll_s)


def restore(resolve, project, w):
    """Przywraca jezyk transkrypcji (z obsluga jezykow rozszerzonych) i strone sprzed skilla."""
    p = os.path.join(w, "transcribe.json")
    if not os.path.exists(p):
        return []
    st = _load(w, "transcribe.json")
    if st.get("lang_before") is not None:
        project.SetSetting("transcriptionLanguage", st["lang_before"])
    if st.get("ext_before") is not None:
        project.SetSetting("transcriptionExtendedLanguageSupport", st["ext_before"])
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
    lang = _load(w, "transcribe.json").get("lang") if os.path.exists(os.path.join(w, "transcribe.json")) else None
    units, counts = {}, {}
    for c in meta["clips"]:
        tr = _transcription(project, c, lang)
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
            segs.append(dict(clip=cid, uid=c["uid"], name=c["name"], fps=fps, s=s, e=e, src_off=c.get("src_off"), ws=sel[0]["s"], we=sel[-1]["e"], i0=i0, i1=i1,
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


def _src_offset(tl, mp, item, rec):
    """Klatka zrodla, od ktorej AppendToTimeline liczy startFrame dla tego klipu. Dla subclipu to jego In w pliku,
    a nie 0 (Resolve 21.1: klatki ponizej In sa dociskane do In i fragment staje sie stopklatka). Kalibracja:
    probne wstawienie od klatki 0 i odczyt GetSourceStartFrame(), potem usuniecie."""
    got = mp.AppendToTimeline([dict(mediaPoolItem=item, startFrame=0, endFrame=1, recordFrame=rec)]) or []
    if not got:
        return 0
    off = int(got[0].GetSourceStartFrame() or 0)
    tl.DeleteClips(got, False)
    return off


def build_timeline(project, w, name, plan=None, pre_s=0.3, post_s=0.4, gap_s=0.0, markers=False):
    """Buduje NOWY timeline z planu (domyslnie zapisany plan.json). Nigdy nie zmienia istniejacych timeline'ow.
    Zwraca raport: liczba klipow, dlugosc, kontrola dziur i nakladek."""
    plan = plan or _load(w, "plan.json")
    sections, errors = resolve_plan(w, plan, pre_s, post_s)
    if errors:
        return dict(ok=False, errors=errors)
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
    placed, warn, offs = [], [], {}
    for si, sec in enumerate(sections):
        if si and gap_f:
            rec += gap_f
        sec_start = rec
        for g in sec["segs"]:
            item = clip_by_uid(project, g["uid"])
            if g["uid"] not in offs:
                offs[g["uid"]] = g["src_off"] if g.get("src_off") is not None else _src_offset(tl, mp, item, rec)
            off = offs[g["uid"]]
            info = dict(mediaPoolItem=item, startFrame=off + g["s"],
                        endFrame=off + (g["e"] if END_EXCLUSIVE else g["e"] - 1), recordFrame=rec)
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
            src = [x for x in got if x.GetSourceEndFrame() is not None]
            if src and min(int(x.GetSourceEndFrame()) - int(x.GetSourceStartFrame()) for x in src) < (g["e"] - g["s"]) // 2:
                warn.append("%s %s: zakres zrodla za krotki (stopklatka?)" % (g["clip"], g["tc"]))
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
    log = _load(w, "builds.json") if os.path.exists(os.path.join(w, "builds.json")) else []
    log.append(dict(name=name, plan=plan, at=time.strftime("%Y-%m-%d %H:%M")))
    _dump(w, "builds.json", log)
    return dict(ok=not [x for x in warn if x.startswith(("nie dodano", "nakladka"))], timeline=name, clips=len(placed),
                duration=fmt_mmss(total), duration_s=round(total, 2), warnings=warn)

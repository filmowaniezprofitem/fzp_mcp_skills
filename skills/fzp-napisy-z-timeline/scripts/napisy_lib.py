# napisy_lib - biblioteka skilla "fzp-napisy-z-timeline". Nie edytuj recznie.
# Copyright (c) 2026 Marcin / Filmowanie z Profitem (filmowaniezprofitem.pl)
# Licencja: MIT + Commons Clause (zob. LICENSE w repozytorium fzp_mcp_skills)
import json, os, re, sys, time

LIB_VERSION = "3.1.1"
MIN_RESOLVE = (21, 1)
BACKUP_PRESET = "_napisy_backup"
TC_DF = False  # drop-frame do wyswietlania timecode'ow; ustawiane z inventory w prepare()/build()

PROFILES = {
    # gap_f: przerwa miedzy stykajacymi sie napisami (klatki)
    # close_s: cisza krotsza niz to -> napisy sie stykaja; ext_s: podtrzymanie po ostatnim slowie przy dluzszej ciszy
    # snap_s: przyciaganie do ciec; min_s/max_s: czas napisu; cps: maks. znakow/s (cps_warn: ostrzezenie)
    "montazowy": dict(gap_f=0, close_s=1.0, ext_s=1.0, snap_s=0.5, min_s=5 / 6, max_s=7.0, cps=17.0, cps_warn=15.0),
    "netflix": dict(gap_f=2, close_s=0.5, ext_s=0.5, snap_s=0.5, min_s=5 / 6, max_s=7.0, cps=17.0, cps_warn=15.0),
}
LAYOUTS = {"poziom": (42, 2), "kwadrat": (32, 2), "pion": (24, 3)}

ONE_LETTER = set("a i o u w z".split())
PREP = set(("w we z ze na do od ode po przy przez przeze przed przede za nad nade pod pode o u bez beze dla ku "
            "między miedzy wśród obok koło około oprócz zamiast według wobec ponad poprzez spod znad sprzed zza "
            "poza wokół dookoła mimo naprzeciw").split())
CONJ = set(("i a ale lub albo oraz czy lecz bo że żeby aby gdy kiedy jeśli jeżeli więc ponieważ gdyż choć "
            "chociaż by ani ni zaś jednak natomiast bowiem iż").split())
STARTERS = set(("że żeby aby ale bo więc gdy kiedy jeśli jeżeli ponieważ gdyż choć chociaż lecz jednak "
                "natomiast bowiem zaś a co gdzie jak jaki jaka jakie jakiego jakim jakiej jakich ile ilu "
                "dlaczego czemu skąd dokąd kto czyj czyja czyje iż").split())
ABBR = set("np. itd. itp. tzn. tj. dr. prof. inż. mgr. ul. godz. min. ok. tys. mln. mld. zł. r. w. nr. św. o.c. ks.".split())
PUNCT_END = re.compile(r"[.?!…]+[\"”»)]*$")
NUM = re.compile(r"^\d[\d.,:%]*$")


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
    """Klatki -> timecode. df=None bierze globalne TC_DF. Drop-frame (29,97/59,94) z separatorem ';'."""
    nom = int(round(fps))
    fr = int(fr)
    df = TC_DF if df is None else df
    sep = ":"
    if df and nom in (30, 60):
        drop = 2 if nom == 30 else 4
        per10 = nom * 600 - drop * 9
        per1 = nom * 60 - drop
        d, m = divmod(fr, per10)
        fr += drop * 9 * d + (drop * ((m - drop) // per1) if m > drop else 0)
        sep = ";"
    s, f = divmod(fr, nom)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return "%02d:%02d:%02d%s%02d" % (h, m, s, sep, f)


def f2srt(fr, fps):
    ms = int(round(fr * 1000.0 / fps))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, s, ms)


# ---------------------------------------------------------------- srodowisko
def check_env(resolve):
    """Wersja Resolve i czy spelnia wymagania. Zwraca dict(ok, version, product, reason)."""
    v = ""
    try:
        v = resolve.GetVersionString() or ""
    except Exception:
        pass
    prod = ""
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


def desktop_dir():
    """Pulpit uzytkownika, takze przy przekierowaniu przez OneDrive na Windows."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes
            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]
            g = GUID(0xB4BFCC3A, 0xDB2C, 0x424C, (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p)) == 0:
                path = p.value
                ctypes.windll.ole32.CoTaskMemFree(p)
                if path and os.path.isdir(path):
                    return path
        except Exception:
            pass
        od = os.environ.get("OneDrive")
        if od and os.path.isdir(os.path.join(od, "Desktop")):
            return os.path.join(od, "Desktop")
    return os.path.join(os.path.expanduser("~"), "Desktop")


def safe_name(t):
    return re.sub(r"[^\w\-]+", "_", t).strip("_") or "timeline"


def default_folder(timeline_name):
    return os.path.join(desktop_dir(), "Napisy_" + safe_name(timeline_name))


def new_workdir(folder, timeline_name):
    """Nowy podfolder roboczy W = <folder>/<timeline>_<RRRRMMDD-HHMM>."""
    w = os.path.join(folder, "%s_%s" % (safe_name(timeline_name), time.strftime("%Y%m%d-%H%M")))
    base, k = w, 2
    while os.path.exists(w):
        w = "%s_%d" % (base, k)
        k += 1
    os.makedirs(w)
    return w


def find_abandoned(project, folder=None):
    """Szuka sladow przebiegu, ktory nie zrobil restore: preset kopii ustawien renderu i niezamkniete state.json.
    Zwraca dict(preset, workdirs) - workdirs od najnowszego."""
    preset = BACKUP_PRESET in (project.GetRenderPresetList() or [])
    found = []
    roots = [folder] if folder else []
    try:
        roots += [os.path.join(desktop_dir(), d) for d in os.listdir(desktop_dir()) if d.startswith("Napisy_")]
    except Exception:
        pass
    for r in roots:
        if not r or not os.path.isdir(r):
            continue
        for d in os.listdir(r):
            p = os.path.join(r, d, "state.json")
            if os.path.isfile(p):
                try:
                    st = json.load(open(p, encoding="utf-8"))
                except Exception:
                    continue
                if not st.get("finished"):
                    found.append((os.path.getmtime(p), os.path.join(r, d)))
    return dict(preset=preset, workdirs=[w for _, w in sorted(set(found), reverse=True)])


# ---------------------------------------------------------------- stan projektu
def _folder_path(mp, target):
    def walk(f, path):
        if f.GetUniqueId() == target.GetUniqueId():
            return path
        for sub in f.GetSubFolderList() or []:
            r = walk(sub, path + [sub.GetName()])
            if r is not None:
                return r
        return None
    return walk(mp.GetRootFolder(), [])


def _folder_by_path(mp, path):
    f = mp.GetRootFolder()
    for name in path or []:
        nxt = [x for x in (f.GetSubFolderList() or []) if x.GetName() == name]
        if not nxt:
            return None
        f = nxt[0]
    return f


def snapshot(resolve, project, workdir, force=False):
    """Zapisuje stan projektu. Gdy zostal preset kopii z porzuconego przebiegu, odmawia (najpierw restore
    tamtego przebiegu albo force=True, jesli uzytkownik potwierdzil, ze obecne ustawienia renderu sa poprawne)."""
    preset = BACKUP_PRESET
    if preset in (project.GetRenderPresetList() or []):
        if not force:
            raise RuntimeError("PORZUCONY_PRZEBIEG: w projekcie zostal preset %s z poprzedniego przebiegu. "
                               "Uzyj find_abandoned() i restore() albo snapshot(..., force=True)." % preset)
        project.DeleteRenderPreset(preset)
    os.makedirs(workdir, exist_ok=True)
    tl = project.GetCurrentTimeline()
    mp = project.GetMediaPool()
    st = dict(
        page=resolve.GetCurrentPage(), timeline=tl.GetName(), timeline_id=tl.GetUniqueId(),
        folder=_folder_path(mp, mp.GetCurrentFolder()), render_mode=project.GetCurrentRenderMode(),
        fmt=project.GetCurrentRenderFormatAndCodec(), preset=preset if project.SaveAsNewRenderPreset(preset) else None,
        lang=project.GetSetting("transcriptionLanguage"),
        audio_enabled=[bool(tl.GetIsTrackEnabled("audio", i)) for i in range(1, tl.GetTrackCount("audio") + 1)],
        jobs=[j["JobId"] for j in (project.GetRenderJobList() or [])], created=[], finished=False,
        lib=LIB_VERSION, started=time.strftime("%Y-%m-%d %H:%M"),
    )
    _save_state(workdir, st)
    return st


def _state(workdir):
    return json.load(open(os.path.join(workdir, "state.json"), encoding="utf-8"))


def _save_state(workdir, st):
    json.dump(st, open(os.path.join(workdir, "state.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _timeline(project, st):
    for i in range(1, project.GetTimelineCount() + 1):
        t = project.GetTimelineByIndex(i)
        if t.GetUniqueId() == st["timeline_id"]:
            return t
    return None


def restore(resolve, project, workdir, remove_media=True):
    """Przywraca stan sprzed skilla. Bezpieczne do wielokrotnego wywolania."""
    st = _state(workdir)
    log = []
    tl = _timeline(project, st)
    if tl:
        project.SetCurrentTimeline(tl)
        for i, en in enumerate(st["audio_enabled"], 1):
            if i <= tl.GetTrackCount("audio"):
                tl.SetTrackEnable("audio", i, en)
    for j in project.GetRenderJobList() or []:
        if j["JobId"] not in st["jobs"]:
            project.DeleteRenderJob(j["JobId"])
            log.append("usunieto zadanie renderu " + j["JobId"])
    if st.get("preset"):
        project.LoadRenderPreset(st["preset"])
        project.DeleteRenderPreset(st["preset"])
    project.SetCurrentRenderMode(st["render_mode"])
    if st.get("fmt"):
        project.SetCurrentRenderFormatAndCodec(st["fmt"]["format"], st["fmt"]["codec"])
    if st.get("lang") is not None:
        project.SetSetting("transcriptionLanguage", st["lang"])
    mp = project.GetMediaPool()
    if remove_media:
        for fpath in st.get("created", []):
            for c in _all_clips(mp):
                if c.GetClipProperty("File Path") == fpath:
                    mp.DeleteClips([c])
                    log.append("usunieto z Media Poola " + os.path.basename(fpath))
    f = _folder_by_path(mp, st.get("folder"))
    if f:
        mp.SetCurrentFolder(f)
    if st.get("page"):
        resolve.OpenPage(st["page"])
    st["finished"] = True
    _save_state(workdir, st)
    return log


def _all_clips(mp):
    out = []
    def walk(f):
        out.extend(f.GetClipList() or [])
        for s in f.GetSubFolderList() or []:
            walk(s)
    walk(mp.GetRootFolder())
    return out


def get_bin(mp, name="Napisy"):
    root = mp.GetRootFolder()
    for f in root.GetSubFolderList() or []:
        if f.GetName() == name:
            return f
    return mp.AddSubFolder(root, name)


# ---------------------------------------------------------------- inwentarz i ciecia
def inventory(project):
    tl = project.GetCurrentTimeline()
    s = tl.GetSettings()
    p = project.GetSettings()
    g = lambda k: (s.get(k) if isinstance(s, dict) and s.get(k) not in (None, "") else p.get(k))
    w, h = int(g("timelineResolutionWidth")), int(g("timelineResolutionHeight"))
    ratio = w / float(h)
    orient = "poziom" if ratio > 1.2 else ("pion" if ratio < 0.8 else "kwadrat")
    audio = []
    for i in range(1, tl.GetTrackCount("audio") + 1):
        audio.append(dict(track=i, name=tl.GetTrackName("audio", i), enabled=bool(tl.GetIsTrackEnabled("audio", i)),
                          clips=sorted({it.GetName() for it in (tl.GetItemListInTrack("audio", i) or [])})))
    return dict(timeline=tl.GetName(), fps=float(g("timelineFrameRate")), df=str(g("timelineDropFrameTimecode")) == "1",
                res=[w, h], orientation=orient, layout=LAYOUTS[orient], start_tc=tl.GetStartTimecode(),
                start_frame=tl.GetStartFrame(), end_frame=tl.GetEndFrame(), audio=audio,
                lang=project.GetSetting("transcriptionLanguage"),
                subtitle_tracks=tl.GetTrackCount("subtitle"))


def compute_cuts(tl):
    """Ciecia = zmiany najwyzszego widocznego klipu wideo (bez tytulow, generatorow, wylaczonych sciezek i klipow)."""
    st, en = tl.GetStartFrame(), tl.GetEndFrame()
    items = []
    for i in range(1, tl.GetTrackCount("video") + 1):
        if not tl.GetIsTrackEnabled("video", i):
            continue
        for it in tl.GetItemListInTrack("video", i) or []:
            try:
                if not it.GetClipEnabled():
                    continue
            except Exception:
                pass
            try:
                if it.GetMediaPoolItem() is None:  # tytuly, Text+, generatory, adjustment clip
                    continue
            except Exception:
                pass
            items.append((int(round(it.GetStart())), int(round(it.GetEnd())), i, it.GetUniqueId()))
    bounds = sorted({b for a, e, _, _ in items for b in (a, e)} - {st, en})
    def top(t):
        best = None
        for a, e, trk, uid in items:
            if a <= t < e and (best is None or trk > best[0]):
                best = (trk, uid)
        return best
    return [b for b in bounds if top(b - 1) != top(b)]


# ---------------------------------------------------------------- render i transkrypcja
def start_render(project, workdir, dialog_tracks, name=None):
    """Renderuje tylko wskazane sciezki audio (numery 1..n) do WAV. Zwraca dict(job, wav)."""
    tl = project.GetCurrentTimeline()
    name = name or "%s_dialog_%d" % (safe_name(tl.GetName()), int(time.time()))
    st = _state(workdir)
    for i in range(1, tl.GetTrackCount("audio") + 1):
        tl.SetTrackEnable("audio", i, i in dialog_tracks)
    project.SetCurrentRenderMode(1)
    project.SetRenderSettings({"SelectAllFrames": True, "ExportVideo": False, "ExportAudio": True,
                               "AudioFormat": "wav", "AudioCodec": "lpcm", "AudioBitDepth": 24,
                               "AudioSampleRate": 48000, "TargetDir": workdir, "CustomName": name})
    job = project.AddRenderJob()
    if not job or not project.StartRendering(job):
        raise RuntimeError("Nie udalo sie uruchomic renderu audio")
    st.setdefault("render_jobs", []).append(job)
    _save_state(workdir, st)
    return dict(job=job, wav=os.path.join(workdir, name + ".wav"))


def render_done(project, job, wait_s=45):
    t0 = time.time()
    while project.IsRenderingInProgress() and time.time() - t0 < wait_s:
        time.sleep(1)
    s = project.GetRenderJobStatus(job) or {}
    return s.get("JobStatus"), s.get("CompletionPercentage")


def import_and_transcribe(resolve, project, workdir, wav_path, speakers=True):
    """Przywraca sciezki audio, importuje WAV do binu Napisy i startuje transkrypcje (na stronie Edit)."""
    st = _state(workdir)
    tl = _timeline(project, st)
    for i, en in enumerate(st["audio_enabled"], 1):
        tl.SetTrackEnable("audio", i, en)
    for j in st.get("render_jobs", []):
        project.DeleteRenderJob(j)
    project.LoadRenderPreset(st["preset"]) if st.get("preset") else None
    project.SetCurrentRenderMode(st["render_mode"])
    if project.GetSetting("transcriptionLanguage") != "pl":
        project.SetSetting("transcriptionLanguage", "pl")
    mp = project.GetMediaPool()
    mp.SetCurrentFolder(get_bin(mp))
    clips = mp.ImportMedia([wav_path]) or []
    if not clips:
        raise RuntimeError("Import WAV nie powiodl sie")
    st.setdefault("created", []).append(wav_path)
    _save_state(workdir, st)
    resolve.OpenPage("edit")
    return clips[0].TranscribeAudio(bool(speakers), False)


def _clip_by_path(project, path):
    for c in _all_clips(project.GetMediaPool()):
        if c.GetClipProperty("File Path") == path:
            return c
    return None


def transcription_ready(project, wav_path):
    c = _clip_by_path(project, wav_path)
    tr = c.GetTranscription() if c else None
    segs = (tr or {}).get("segments") or []
    return len(segs)


def wait_transcription(project, wav_path, wait_s=50, poll_s=5):
    """Czeka do wait_s sekund w jednym wywolaniu. Zwraca liczbe segmentow (0 = jeszcze nie gotowe)."""
    t0 = time.time()
    while True:
        n = transcription_ready(project, wav_path)
        if n or time.time() - t0 >= wait_s:
            return n
        time.sleep(poll_s)


def export_words(project, workdir, wav_path, track_label=None, fix=True):
    """Czyta transkrypcje WAV, przelicza na klatki timeline'u, zapisuje words.json. Zwraca liczbe slow."""
    st = _state(workdir)
    tl = _timeline(project, st)
    inv = inventory(project)
    fps = exact_fps(inv["fps"])
    c = _clip_by_path(project, wav_path)
    cfps = exact_fps(c.GetClipProperty("FPS") or inv["fps"])
    c0 = tc2f(c.GetClipProperty("Start TC") or "00:00:00:00", cfps, inv["df"])
    words = []
    for seg in (c.GetTranscription() or {}).get("segments") or []:
        first = True
        for w in seg.get("words") or []:
            t = (w.get("text") or "").strip()
            if not t or t == "(...)":
                continue
            s = (tc2f(w["start"], cfps, inv["df"]) - c0) / cfps
            e = (tc2f(w["end"], cfps, inv["df"]) - c0) / cfps
            words.append(dict(t=t, s=inv["start_frame"] + int(round(s * fps)), e=inv["start_frame"] + int(round(e * fps)),
                              sp=track_label or seg.get("speaker") or "S1", first=first))
            first = False
    if fix:
        fix_stretched(words, fps)
    path = os.path.join(workdir, "words.json")
    old = _load(workdir, "words.json") if (track_label and os.path.exists(path)) else []
    allw = sorted(old + words, key=lambda w: (w["s"], w["e"]))
    _dump(workdir, "words.json", allw)
    _dump(workdir, "timeline.json", dict(cuts=compute_cuts(tl), inv=inv))
    return len(words)


def fix_stretched(words, fps):
    """Pierwsze slowo segmentu (po ciszy) bywa rozciagniete na cala cisze: wiarygodny jest koniec, start skracamy."""
    for w in words:
        if not w.get("first"):
            continue
        n = max(1, len(re.sub(r"[^\w]", "", w["t"])))
        dur_ms = (w["e"] - w["s"]) * 1000.0 / fps
        if dur_ms > max(400, 150 * n):
            w["s"] = w["e"] - max(1, int(round(max(200, 80 * n) / 1000.0 * fps)))


# ---------------------------------------------------------------- tekst: jednostki (zdania skladowe)
def _bare(t):
    return re.sub(r"^[\"„«(…\-–]+|[\"”»),.;:?!…\-–]+$", "", t).lower()


def _sentence_end(t):
    return bool(PUNCT_END.search(t)) and t.lower() not in ABBR


def default_units(words, fps, P):
    close = P["close_s"] * fps  # dluga cisza w srodku zdania (> 2 s) tez dzieli
    units, cur = [], []
    for i, w in enumerate(words):
        if cur:
            p = words[i - 1]
            hard = _sentence_end(p["t"]) or p["sp"] != w["sp"] or (w["s"] - p["e"]) > max(close, 2 * fps)
            nb = _bare(w["t"])
            nn = _bare(words[i + 1]["t"]) if i + 1 < len(words) else ""
            rel = lambda x: x in STARTERS or x.startswith("któr")
            soft = p["t"][-1:] in ",;:–" and (rel(nb) or (nb in PREP and rel(nn)))
            if hard or soft:
                units.append(cur)
                cur = []
        cur.append(i)
    if cur:
        units.append(cur)
    return units


def units_text(words, units, fps):
    out = []
    for n, u in enumerate(units, 1):
        out.append("U%d %s [%s] %s" % (n, f2tc(words[u[0]]["s"], fps), words[u[0]]["sp"],
                                       " ".join(words[i]["t"] for i in u)))
    return "\n".join(out)


def _norm(t):
    return re.sub(r"[^\w]", "", t.lower())


def _find(seq, phrase):
    toks = phrase.split()
    for cmp in (lambda a, b: a == b, lambda a, b: _norm(a) == _norm(b)):
        for k in range(len(seq) - len(toks) + 1):
            if all(cmp(seq[k + j]["t"], toks[j]) for j in range(len(toks))):
                return k, len(toks)
    return None


def apply_plan(words, units, plan):
    """plan = {"edits":[{"u":1,"old":"odra","new":"Odra"}], "split":[{"u":4,"before":"przed atakiem"}],
               "join":[3], "drop":[7], "speakers":{"12":"B"}}. Numery U z units_text. Zwraca (lista jednostek z kopiami slow, bledy)."""
    errors = []
    U = [[dict(words[i]) for i in u] for u in units]
    for un, spk in (plan.get("speakers") or {}).items():  # recznie wskazany mowca jednostki
        for w in U[int(un) - 1]:
            w["sp"] = spk
    for ed in plan.get("edits", []):
        u = U[ed["u"] - 1]
        hit = _find(u, ed["old"])
        if not hit:
            errors.append("U%d: nie znaleziono '%s'" % (ed["u"], ed["old"]))
            continue
        k, n = hit
        old = u[k:k + n]
        new = ed.get("new", "").split()
        s, e = old[0]["s"], old[-1]["e"]
        if len(new) == len(old):
            rep = [dict(o, t=t) for o, t in zip(old, new)]
        else:
            tot = sum(len(t) for t in new) or 1
            rep, acc = [], 0
            for t in new:
                a = s + int(round((e - s) * acc / tot))
                acc += len(t)
                rep.append(dict(t=t, s=a, e=s + int(round((e - s) * acc / tot)), sp=old[0]["sp"]))
        U[ed["u"] - 1] = u[:k] + rep + u[k + n:]
    splits = {}
    for sp in plan.get("split", []):
        splits.setdefault(sp["u"], []).append(sp["before"])
    join, drop = set(plan.get("join", [])), set(plan.get("drop", []))
    out = []
    pending_join = False
    for n, u in enumerate(U, 1):
        if n in drop or not u:
            pending_join = False
            continue
        parts = [u]
        for phrase in splits.get(n, []):
            last = parts[-1]
            hit = _find(last[1:], phrase)
            if not hit:
                errors.append("U%d: nie znaleziono miejsca podzialu '%s'" % (n, phrase))
                continue
            k = hit[0] + 1
            parts[-1:] = [last[:k], last[k:]]
        if pending_join and out:
            out[-1] = out[-1] + parts[0]
            parts = parts[1:]
        out.extend(parts)
        pending_join = n in join
    return out, errors


# ---------------------------------------------------------------- lamanie wierszy
def _break_cost(a, b):
    ba, bb = _bare(a), _bare(b)
    c = 0
    if ba in ONE_LETTER or ba in PREP or ba in CONJ or ba == "nie":
        c += 100
    if NUM.match(ba):
        c += 60
    if ba == "się" or bb == "się":
        c += 30
    if a[:1].isupper() and b[:1].isupper() and not _sentence_end(a):
        c += 40
    if a[-1:] in ",.;:?!…–":
        c -= 20
    if bb in STARTERS or bb in PREP or bb in CONJ:
        c -= 10
    return c


def _ln(ws):
    return len(" ".join(ws))


def layout_unit(ws, M, L):
    """Najlepszy podzial listy slow (tekstow) na <= L wierszy po <= M znakow. None, gdy sie nie da."""
    if _ln(ws) <= M:
        return [ws], 0
    best = None
    n = len(ws)
    if L >= 2:
        for k in range(1, n):
            a, b = ws[:k], ws[k:]
            la, lb = _ln(a), _ln(b)
            if la <= M and lb <= M:
                c = _break_cost(ws[k - 1], ws[k]) + abs(la - lb) * 0.5 + (5 if la > lb else 0)
                if best is None or c < best[1]:
                    best = ([a, b], c)
    if best is None and L >= 3:
        for k in range(1, n - 1):
            for j in range(k + 1, n):
                parts = [ws[:k], ws[k:j], ws[j:]]
                ls = [_ln(p) for p in parts]
                if max(ls) <= M:
                    c = _break_cost(ws[k - 1], ws[k]) + _break_cost(ws[j - 1], ws[j]) + (max(ls) - min(ls)) * 0.5
                    if best is None or c < best[1]:
                        best = (parts, c)
    return best if best else None


def layout_sub(units, M, L):
    texts = [[w["t"] for w in u] for u in units]
    flat = [t for u in texts for t in u]
    if len(units) == 1:
        return layout_unit(flat, M, L)
    if L >= 2 and len(units) <= L and all(_ln(u) <= M for u in texts):
        return texts, 0  # kazde zdanie skladowe w osobnym wierszu
    if L == 1 and _ln(flat) <= M:
        return [flat], 0
    return None


# ---------------------------------------------------------------- napisy
def _mk(units):
    ws = [w for u in units for w in u]
    return dict(units=units, ws=ws[0]["s"], we=ws[-1]["e"], sp=ws[0]["sp"])


def split_long(units_words, fps, P, M, L):
    """Dzieli jednostki, ktore nie mieszcza sie w napisie lub trwaja dluzej niz max_s."""
    maxf = P["max_s"] * fps
    out, warn = [], []
    stack = list(units_words)[::-1]
    while stack:
        u = stack.pop()
        if (layout_unit([w["t"] for w in u], M, L) and u[-1]["e"] - u[0]["s"] <= maxf) or len(u) < 2:
            if not layout_unit([w["t"] for w in u], M, L):
                warn.append("%s slowo dluzsze niz %d znakow: %s" % (f2tc(u[0]["s"], fps), M, u[0]["t"]))
            out.append(u)
            continue
        best = None
        tot = _ln([w["t"] for w in u])
        for k in range(1, len(u)):
            la = _ln([w["t"] for w in u[:k]])
            pause = (u[k]["s"] - u[k - 1]["e"]) / fps
            c = _break_cost(u[k - 1]["t"], u[k]["t"]) + abs(la - (tot - la)) * 0.3 - pause * 30
            if best is None or c < best[1]:
                best = (k, c)
        k = best[0]
        stack.append(u[k:])
        stack.append(u[:k])
    return out, warn


def compute_timing(subs, cuts, fps, P, tl_end):
    F = lambda sec: int(round(sec * fps))
    gap, close, ext, snap = P["gap_f"], F(P["close_s"]), F(P["ext_s"]), F(P["snap_s"])
    dmin, dmax = F(P["min_s"]), F(P["max_s"])
    n = len(subs)
    for i, s in enumerate(subs):  # nakladajacy sie mowcy: napis startuje po poprzednim
        if i and s["ws"] < subs[i - 1]["we"]:
            s["ws"] = min(subs[i - 1]["we"], s["we"] - 1)
        s["st"], s["en"] = s["ws"], s["we"]
    for i, s in enumerate(subs):  # przyciaganie startu
        lo = subs[i - 1]["we"] + gap if i else -10 ** 9
        for c in cuts:
            if 0 < s["ws"] - c <= snap and c >= lo:
                s["st"] = c
                break
            if 0 < c - s["ws"] < snap and s["we"] > c:
                s["st"] = c - snap if c - snap >= lo else c
                break
    for i, s in enumerate(subs):  # koniec: styk / podtrzymanie / ciecia
        nx = subs[i + 1] if i + 1 < n else None
        prev_en = subs[i - 1]["en"] if i else -10 ** 9
        s["st"] = max(s["st"], prev_en + (gap if prev_en > -10 ** 8 else 0))
        ncut = min([c for c in cuts if c > s["we"]], default=None)
        lim = nx["st"] - gap if nx else tl_end
        if nx and nx["st"] - s["we"] <= close:
            en = lim
        else:
            en = s["we"] + ext
            if nx and nx["st"] - en < close:
                en = lim
        if ncut is not None and ncut < en:
            if nx and nx["st"] > ncut and nx["st"] - ncut <= close and nx["st"] - s["we"] <= close:
                nx["st"] = ncut
            en = ncut - (gap if nx and nx["st"] <= ncut + snap else 0)
        elif ncut is not None and 0 < ncut - en <= snap and ncut <= lim + gap:
            en = ncut - (gap if nx and nx["st"] <= ncut else 0)
        en = min(en, lim, tl_end)
        en = max(en, min(s["we"], lim))
        if en - s["st"] > dmax:
            en = max(s["we"], s["st"] + dmax)
            if nx and gap < nx["st"] - en < close and nx["st"] - (en + gap) <= snap:
                nx["st"] = en + gap  # nastepny napis wchodzi chwile wczesniej zamiast migniecia
        if en - s["st"] < dmin:  # wydluz w wolne miejsce, nie przez ciecie
            hard = min([x for x in [lim, tl_end, (ncut - (gap if nx and nx["st"] <= ncut else 0)) if ncut else None] if x is not None])
            en = max(en, min(s["st"] + dmin, hard))
            if en - s["st"] < dmin:
                pcut = max([c for c in cuts if c <= s["st"]], default=-10 ** 9)
                lo = max(prev_en + gap, pcut, s["st"] - (dmin - (en - s["st"])))
                if lo < s["st"]:
                    s["st"] = lo
        s["en"] = en
    return subs


def borrow_time(subs, cuts, fps, P):
    """Krotkie napisy pozyczaja czas od stykajacych sie sasiadow (Netflix: borrowing time).
    Sasiad zostaje >= min_s, a jego start moze sie spoznic wzgledem mowy najwyzej o snap_s."""
    F = lambda sec: int(round(sec * fps))
    gap, dmin, snap = P["gap_f"], F(P["min_s"]), F(P["snap_s"])
    for _ in range(3):
        for i, s in enumerate(subs):
            need = dmin - (s["en"] - s["st"])
            if need <= 0:
                continue
            if i + 1 < len(subs):
                nx = subs[i + 1]
                if nx["st"] - s["en"] == gap and not any(s["en"] <= c <= nx["st"] + need for c in cuts):
                    d = max(0, min(need, nx["ws"] + snap - nx["st"], (nx["en"] - nx["st"]) - dmin))
                    s["en"] += d
                    nx["st"] += d
                    need -= d
            if need > 0 and i:
                pv = subs[i - 1]
                if s["st"] - pv["en"] == gap and not any(pv["en"] - need <= c <= s["st"] for c in cuts):
                    d = max(0, min(need, pv["en"] - pv["we"], (pv["en"] - pv["st"]) - dmin))
                    s["st"] -= d
                    pv["en"] -= d
    return subs


def _chars(s):
    return sum(len(" ".join(w["t"] for w in u)) for u in s["units"])


def _flags(s, fps, P):
    dur = (s["en"] - s["st"]) / fps
    return dict(short=dur < P["min_s"] - 1e-6, fast=dur > 0 and _chars(s) / dur > P["cps"])


def build_subs(units_words, cuts, fps, P, M, L, tl_end, merge=True):
    parts, warn = split_long(units_words, fps, P, M, L)
    subs = [_mk([u]) for u in parts]
    maxf = P["max_s"] * fps
    close = P["close_s"] * fps
    for _ in range(50):
        compute_timing(subs, cuts, fps, P, tl_end)
        if not merge:
            break
        changed = False
        for i, s in enumerate(subs):
            fl = _flags(s, fps, P)
            if not (fl["short"] or fl["fast"]):
                continue
            cand = []
            for j in (i - 1, i + 1):
                if 0 <= j < len(subs):
                    a, b = (subs[j], s) if j < i else (s, subs[j])
                    if a["sp"] != b["sp"] or len(a["units"]) + len(b["units"]) > max(L, 1):
                        continue
                    if _sentence_end(a["units"][-1][-1]["t"]):
                        continue  # laczymy tylko czesci jednego zdania: inne zdanie moze nalezec do innej osoby
                    if b["ws"] - a["we"] > close or b["we"] - a["ws"] > maxf:
                        continue
                    if any(a["we"] < c <= b["ws"] for c in cuts):
                        continue
                    if not layout_sub(a["units"] + b["units"], M, L):
                        continue
                    cand.append((b["we"] - a["ws"], min(i, j)))
            if cand:
                k = min(cand)[1]
                subs[k:k + 2] = [_mk(subs[k]["units"] + subs[k + 1]["units"])]
                changed = True
                break
        if not changed:
            break
    borrow_time(subs, cuts, fps, P)
    for s in subs:
        lay = layout_sub(s["units"], M, L)
        s["lines"] = [" ".join(l) for l in lay[0]] if lay else [" ".join(w["t"] for u in s["units"] for w in u)]
        s["break_cost"] = lay[1] if lay else 999
    return subs, warn


def validate(subs, words_total, cuts, fps, P, M, L):
    W = []
    gap, close = P["gap_f"], P["close_s"] * fps
    n_words = 0
    for i, s in enumerate(subs):
        tc = f2tc(s["st"], fps)
        n_words += sum(len(u) for u in s["units"])
        dur = (s["en"] - s["st"]) / fps
        txt = " / ".join(s["lines"])
        if len(s["lines"]) > L or any(len(l) > M for l in s["lines"]):
            W.append("%s za dlugi wiersz lub za duzo wierszy: %s" % (tc, txt))
        if s["break_cost"] >= 100:
            W.append("%s niezreczne lamanie wiersza: %s" % (tc, txt))
        if dur < P["min_s"] - 1e-6:
            W.append("%s krotki napis %.2f s: %s" % (tc, dur, txt))
        if dur > P["max_s"] + 1e-6:
            W.append("%s dlugi napis %.1f s: %s" % (tc, dur, txt))
        cps = _chars(s) / dur if dur > 0 else 99
        if cps > P["cps_warn"]:
            W.append("%s szybki napis %.1f zn/s: %s" % (tc, cps, txt))
        for c in cuts:
            if s["st"] < c < s["en"] and not (s["ws"] < c < s["we"]):
                W.append("%s napis przechodzi przez ciecie %s" % (tc, f2tc(c, fps)))
        if i + 1 < len(subs):
            g = subs[i + 1]["st"] - s["en"]
            if g < 0:
                W.append("%s naklada sie na nastepny" % tc)
            elif g != gap and g < close:
                W.append("%s przerwa %d kl. przed nastepnym (migniecie)" % (tc, g))
    if n_words != words_total:
        W.append("liczba slow w napisach (%d) rozna od transkrypcji po korektach (%d)" % (n_words, words_total))
    return W


def srt_text(subs, fps, start_frame):
    out = []
    for i, s in enumerate(subs, 1):
        out.append("%d\n%s --> %s\n%s\n" % (i, f2srt(s["st"] - start_frame, fps), f2srt(s["en"] - start_frame, fps),
                                             "\n".join(s["lines"])))
    return "\n".join(out)


# ---------------------------------------------------------------- przebiegi wywolywane ze skilla
def _load(workdir, name):
    return json.load(open(os.path.join(workdir, name), encoding="utf-8"))


def _dump(workdir, name, obj):
    json.dump(obj, open(os.path.join(workdir, name), "w", encoding="utf-8"), ensure_ascii=False)


def prepare(workdir, profile="montazowy"):
    """Po export_words: tworzy domyslne jednostki i zwraca tekst do przegladu przez model."""
    global TC_DF
    words = _load(workdir, "words.json")
    meta = _load(workdir, "timeline.json")
    TC_DF = bool(meta["inv"].get("df"))
    fps = exact_fps(meta["inv"]["fps"])
    P = PROFILES[profile]
    units = default_units(words, fps, P)
    _dump(workdir, "units.json", units)
    return units_text(words, units, fps)


def build(workdir, plan, profile="montazowy", max_chars=None, max_lines=None, merge=True, per_speaker=False,
          tc_clock=False):
    """Stosuje plan, buduje napisy, waliduje i zapisuje SRT. Zwraca dict z podgladem i ostrzezeniami.
    files: SRT do wstawienia w Resolve - czasy = bezwzgledny timecode timeline'u (Insert ... Using Timecode
    czyta SRT bezwzglednie). delivery: SRT dla klienta od 00:00:00 (tylko gdy timeline nie startuje od zera).
    tc_clock=True: plik do Resolve liczony wg nominalnego FPS (timecode), na wypadek przesuniecia przy 23,976/29,97."""
    global TC_DF
    words = _load(workdir, "words.json")
    units = _load(workdir, "units.json")
    meta = _load(workdir, "timeline.json")
    inv, cuts = meta["inv"], meta["cuts"]
    TC_DF = bool(inv.get("df"))
    fps = exact_fps(inv["fps"])
    P = PROFILES[profile]
    M = max_chars or inv["layout"][0]
    L = max_lines or inv["layout"][1]
    plan = plan or {}
    uw, errors = apply_plan(words, units, plan)
    if errors:
        return dict(errors=errors)
    _dump(workdir, "plan.json", plan)
    _dump(workdir, "params.json", dict(profile=profile, max_chars=M, max_lines=L, merge=merge,
                                       per_speaker=per_speaker, tc_clock=tc_clock))
    total = sum(len(u) for u in uw)
    groups = {}
    if per_speaker:
        for u in uw:
            groups.setdefault(u[0]["sp"], []).append(u)
    else:
        groups = {"": uw}
    res = dict(files=[], delivery=[], preview=[], warnings=[], warnings_soft=[], counts={})
    for sp, gu in groups.items():
        subs, warn = build_subs(gu, cuts, fps, P, M, L, inv["end_frame"], merge)
        warn += validate(subs, sum(len(u) for u in gu), cuts, fps, P, M, L)
        tag = ("_" + re.sub(r"\W+", "", sp)) if sp else ""
        v = 1
        stem = "%s_PL_%s%s" % (safe_name(inv["timeline"]), inv["orientation"], tag)
        while os.path.exists(os.path.join(workdir, "%s_v%d.srt" % (stem, v))):
            v += 1
        path = os.path.join(workdir, "%s_v%d.srt" % (stem, v))
        open(path, "w", encoding="utf-8", newline="\n").write(srt_text(subs, round(fps) if tc_clock else fps, 0))
        res["files"].append(path)
        if inv["start_frame"]:
            dpath = path[:-4] + "_od_zera.srt"
            open(dpath, "w", encoding="utf-8", newline="\n").write(srt_text(subs, fps, inv["start_frame"]))
            res["delivery"].append(dpath)
        res["counts"][sp or "all"] = len(subs)
        for x in warn:  # 15-17 zn/s to normalne tempo mowy: osobna lista, w raporcie tylko liczba
            m = re.search(r"szybki napis ([\d.]+) zn/s", x)
            (res["warnings_soft"] if m and float(m.group(1)) <= P["cps"] else res["warnings"]).append(x)
        res["preview"] += ["%s-%s %s" % (f2tc(s["st"], fps), f2tc(s["en"], fps), " / ".join(s["lines"])) for s in subs]
        json.dump([dict(st=s["st"], en=s["en"], lines=s["lines"]) for s in subs],
                  open(path[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False)
    res["params"] = dict(profile=profile, max_chars=M, max_lines=L, words=total)
    return res


def rebuild(workdir, plan_patch=None, **overrides):
    """Przebudowa bez renderu i transkrypcji: bierze zapisany plan.json i params.json, nadpisuje wskazane
    parametry (np. profile="netflix", max_chars=37). plan_patch dokleja nowe pozycje do list planu."""
    plan = _load(workdir, "plan.json") if os.path.exists(os.path.join(workdir, "plan.json")) else {}
    params = _load(workdir, "params.json") if os.path.exists(os.path.join(workdir, "params.json")) else {}
    for k, v in (plan_patch or {}).items():
        if isinstance(v, list):
            plan[k] = (plan.get(k) or []) + v
        elif isinstance(v, dict):
            plan[k] = dict(plan.get(k) or {}, **v)
        else:
            plan[k] = v
    params.update(overrides)
    return build(workdir, plan, **params)


def import_srt(project, path):
    mp = project.GetMediaPool()
    mp.SetCurrentFolder(get_bin(mp))
    items = mp.ImportMedia([path]) or []
    if not items:
        return None
    mp.SetSelectedClip(items[0])
    tl = project.GetCurrentTimeline()
    tl.SetCurrentTimecode(tl.GetStartTimecode())
    return items[0].GetName()


def verify(project, srt_path, fps=None):
    """Po wstawieniu napisow przez uzytkownika: szuka sciezki z tymi napisami i porownuje pierwszy i ostatni."""
    tl = project.GetCurrentTimeline()
    exp = json.load(open(srt_path[:-4] + ".json", encoding="utf-8"))
    best = None
    for i in range(1, tl.GetTrackCount("subtitle") + 1):
        items = tl.GetItemListInTrack("subtitle", i) or []
        names = [it.GetName() for it in items]
        if names and (names[0].replace("\n", " ") == " ".join(exp[0]["lines"]) or len(items) == len(exp)):
            best = (i, items)
    if not best:
        return dict(ok=False, reason="nie znaleziono sciezki z napisami")
    i, items = best
    f0 = int(round(items[0].GetStart())) - exp[0]["st"]
    fl = int(round(items[-1].GetStart())) - exp[-1]["st"]
    return dict(ok=len(items) == len(exp) and f0 == 0 and fl == 0, track=i, count=len(items), expected=len(exp),
                offset_first=f0, offset_last=fl)

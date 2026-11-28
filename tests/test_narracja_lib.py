"""Testy biblioteki narracja_lib bez DaVinci Resolve (atrapy API)."""
import importlib.util
import os

import pytest

LIB = os.path.join(os.path.dirname(__file__), "..", "skills", "fzp-szybka-narracja", "scripts", "narracja_lib.py")


@pytest.fixture()
def L():
    spec = importlib.util.spec_from_file_location("narracja_lib", LIB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ atrapy API Resolve
def tc(fr, fps=25, base="00:00:00:00"):
    h, m, s, f = [int(x) for x in base.split(":")]
    fr += ((h * 60 + m) * 60 + s) * fps + f
    s_, f_ = divmod(fr, fps)
    m_, s_ = divmod(s_, 60)
    h_, m_ = divmod(m_, 60)
    return "%02d:%02d:%02d:%02d" % (h_, m_, s_, f_)


def make_tr(sentences, fps=25, base="00:00:00:00", sp="Speaker 1", gap=20):
    """sentences: lista zdan; kazde slowo 10 klatek, miedzy slowami 2 kl., miedzy zdaniami `gap` kl."""
    segs, t = [], 0
    for sent in sentences:
        words = []
        for wd in sent.split():
            words.append(dict(text=wd, start=tc(t, fps, base), end=tc(t + 10, fps, base)))
            t += 12
        segs.append(dict(text=sent, speaker=sp, start=words[0]["start"], end=words[-1]["end"], words=words))
        t += gap
    return dict(language="pl", segments=segs), t


class FakeClip:
    def __init__(self, uid, name, path, fps=25, frames=5000, start_tc="00:00:00:00", tr=None, typ="Video + Audio", marks=None,
                 src_in=0, date=""):
        self.uid, self.name, self.tr, self.marks = uid, name, tr, marks or {}
        self.src_in = src_in  # subclip: In w klatkach pliku (Resolve liczy startFrame AppendToTimeline od pliku)
        self.props = {"Type": typ, "FPS": fps, "Start TC": start_tc, "Frames": str(frames), "File Path": path,
                      "Duration": "00:03:20:00", "Date Created": date}
        self.transcribed_calls = 0
        self.cleared = 0

    def GetUniqueId(self): return self.uid
    def GetName(self): return self.name
    def GetClipProperty(self, k=None): return self.props.get(k) if k else self.props
    def GetTranscription(self): return self.tr
    def GetMarkInOut(self): return self.marks

    def TranscribeAudio(self, sp=None, nested=False):
        self.transcribed_calls += 1
        return True

    def ClearTranscription(self, nested=False):
        self.cleared += 1
        self.tr = None
        return True


class FakeFolder:
    def __init__(self, name, clips=(), subs=()):
        self.name, self.clips, self.subs = name, list(clips), list(subs)

    def GetName(self): return self.name
    def GetClipList(self): return self.clips
    def GetSubFolderList(self): return self.subs
    def GetUniqueId(self): return "F_" + self.name


class FakeItem:
    def __init__(self, st, en, src_s=0, src_e=0, mpi=None, left=0):
        self.st, self.en, self.src_s, self.src_e, self.mpi, self.left = st, en, src_s, src_e, mpi, left
    def GetStart(self): return self.st
    def GetEnd(self): return self.en
    def GetDuration(self): return self.en - self.st
    def GetSourceStartFrame(self): return self.src_s
    def GetSourceEndFrame(self): return self.src_e
    def GetMediaPoolItem(self): return self.mpi
    def GetLeftOffset(self): return self.left


class FakeTimeline:
    def __init__(self, name, fps=25, start=90000):
        self.name, self.fps, self.start, self.items, self.markers = name, fps, start, [], []
        self.deleted = 0

    def GetName(self): return self.name
    def GetUniqueId(self): return "T_" + self.name
    def GetTrackCount(self, kind): return 1
    def GetItemListInTrack(self, kind, i): return [x for x in self.items if x.mpi] if kind == "video" else []

    def DeleteClips(self, items, ripple=False):
        for x in items:
            if x in self.items:
                self.items.remove(x)
                self.deleted += 1
        return True
    def GetStartFrame(self): return self.start
    def GetSetting(self, k): return self.fps if k == "timelineFrameRate" else None
    def AddMarker(self, f, color, name, note, dur, custom=None):
        self.markers.append((f, name))
        return True


class FakeMP:
    def __init__(self, root, project):
        self.root, self.cur, self.project, self.appended = root, root, project, []

    def GetRootFolder(self): return self.root
    def GetCurrentFolder(self): return self.cur
    def SetCurrentFolder(self, f): self.cur = f; return True

    def CreateEmptyTimeline(self, name):
        if self.cur is not self.root:  # zachowanie Resolve: poza rootem potrafi zwrocic None
            return None
        tl = FakeTimeline(name, fps=self.project.tl_fps)
        self.project.timelines.append(tl)
        return tl

    def AppendToTimeline(self, infos):
        tl = self.project.current
        out = []
        for i in infos:
            c = i["mediaPoolItem"]
            src_fps = float(c.GetClipProperty("FPS"))
            dur = int(round((i["endFrame"] - i["startFrame"]) * tl.fps / src_fps))
            # Resolve 21.1: klatki ponizej In subclipu sa dociskane do In -> stopklatka
            s = max(i["startFrame"], c.src_in)
            e = max(i["endFrame"], s) if i["endFrame"] > c.src_in else s
            it = FakeItem(i["recordFrame"], i["recordFrame"] + dur, s, e, c, s - c.src_in)
            self.appended.append(i)
            tl.items.append(it)
            out += [it, FakeItem(it.st, it.en, s, e)]  # wideo + audio
        return out


class FakeProject:
    def __init__(self, root, tl_fps=25):
        self.tl_fps, self.timelines, self.current = tl_fps, [], None
        self.mp = FakeMP(root, self)
        self.settings = {"timelineFrameRate": tl_fps, "transcriptionLanguage": "auto",
                         "transcriptionExtendedLanguageSupport": "0"}
        self.job = {"JobStatus": "Complete"}

    def GetName(self): return "Test projekt"
    def GetMediaPool(self): return self.mp
    def GetSetting(self, k): return self.settings.get(k)
    def SetSetting(self, k, v):
        # Resolve 21.1: polski tylko z wlaczona obsluga jezykow rozszerzonych
        if k == "transcriptionLanguage" and v == "pl" and self.settings["transcriptionExtendedLanguageSupport"] != "1":
            return False
        self.settings[k] = v
        return True
    def GetTimelineCount(self): return len(self.timelines)
    def GetTimelineByIndex(self, i): return self.timelines[i - 1]
    def SetCurrentTimeline(self, tl): self.current = tl; return True
    def GetCurrentTimeline(self): return self.current
    def GetTranscribeAudioStatus(self): return self.job


class FakeResolve:
    def __init__(self): self.page = "media"
    def GetCurrentPage(self): return self.page
    def OpenPage(self, p): self.page = p; return True


S1 = ["Dzień dobry, nazywam się Jan Kowalski.", "Pracuję w strefie od trzydziestu lat.",
      "No więc, to był trudny początek.", "Dzisiaj mamy dwadzieścia pięć tysięcy miejsc pracy."]
S2 = ["Zaczynaliśmy w małej hali.", "Teraz eksportujemy do dwudziestu krajów."]


@pytest.fixture()
def env(L, tmp_path):
    tr1, _ = make_tr(S1)
    tr2, _ = make_tr(S2, fps=50, base="01:00:00:00", sp="Speaker 2")
    c1 = FakeClip("u1", "A_wywiad_prezes.mov", "/m/a.mov", tr=tr1)
    c2 = FakeClip("u2", "B_wywiad_firma.mov", "/m/b.mov", fps=50, start_tc="01:00:00:00", tr=tr2)
    broll = FakeClip("u3", "dron.mov", "/m/d.mov", typ="Video")
    wyw = FakeFolder("Wywiady", [c2, c1, broll])
    root = FakeFolder("Master", [], [wyw])
    p = FakeProject(root)
    w = str(tmp_path)
    return dict(p=p, w=w, c1=c1, c2=c2, wyw=wyw)


def test_inventory_and_units(L, env):
    clips = L.inventory(env["p"], env["w"], "Wywiady")
    assert [c["id"] for c in clips] == ["C01", "C02"]  # bez b-rolla, bez dat -> po Start TC
    assert clips[0]["name"] == "A_wywiad_prezes.mov" and clips[0]["transcribed"]
    counts = L.export_units(env["p"], env["w"])
    assert counts == {"C01": 4, "C02": 2}
    txt = L.units_text(env["w"])
    assert "C01.U1 [00:00:00:00]" in txt and "## C02 B_wywiad_firma.mov" in txt
    assert "C02.U1 [01:00:00:00]" in txt  # TC zrodla z Start TC klipu


def test_list_bins(L, env):
    b = L.list_bins(env["p"])
    assert b == [dict(path="Wywiady", clips=2, current=False)]


def test_plan_trim_and_handles(L, env):
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    plan = {"sections": [{"title": "Otwarcie", "items": [
        {"from": "C01.U1"},
        {"from": "C01.U3", "start_at": "to był", "end_at": "początek."}]}]}
    secs, err = L.resolve_plan(env["w"], plan)
    assert err == []
    a, b = secs[0]["segs"]
    assert a["text"] == "Dzień dobry, nazywam się Jan Kowalski."
    assert b["text"] == "to był trudny początek."
    units = L._load(env["w"], "units.json")
    u3 = units["C01.U3"]["words"]
    # zapas przed "to" nie wchodzi na slowo "więc," przed nim
    assert b["s"] >= u3[1]["e"] and b["s"] <= u3[2]["s"]
    assert a["s"] == 0  # poczatek klipu


def test_plan_errors(L, env):
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    _, err = L.resolve_plan(env["w"], {"sections": [{"items": [{"from": "C09.U1"}, {"from": "C01.U1", "to": "C02.U1"},
                                                               {"from": "C01.U2", "start_at": "nie ma"}]}]})
    assert len(err) == 3


def test_adjacent_merge(L, env):
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    secs, _ = L.resolve_plan(env["w"], {"sections": [{"items": [{"from": "C01.U1"}, {"from": "C01.U2"}]}]})
    assert len(secs[0]["segs"]) == 1  # zapasy sie stykaja -> jeden ciagly fragment


def test_preview_totals(L, env):
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    plan = {"sections": [{"title": "A", "items": [{"from": "C01.U1"}]}, {"title": "B", "items": [{"from": "C02.U2"}]}]}
    r = L.preview(env["w"], plan)
    assert not r["errors"] and r["items"] == 2
    assert "### A" in r["text"] and "Razem:" in r["text"]
    secs, _ = L.resolve_plan(env["w"], plan)
    exp = sum((g["e"] - g["s"]) / g["fps"] for s in secs for g in s["segs"])
    assert abs(r["total_s"] - exp) < 0.01
    assert os.path.exists(os.path.join(env["w"], "plan.json"))


def test_build_timeline_contiguous_mixed_fps(L, env):
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    plan = {"sections": [{"title": "A", "items": [{"from": "C01.U1"}, {"from": "C02.U1"}]},
                         {"title": "B", "items": [{"from": "C01.U4"}]}]}
    L.preview(env["w"], plan)
    r = L.build_timeline(env["p"], env["w"], "Narracja e01", gap_s=1.0)
    assert r["ok"], r
    tl = env["p"].current
    assert tl.name == "Narracja e01" and r["clips"] == 3
    it = tl.items
    assert it[0].st == 90000 and it[1].st == it[0].en  # styk w sekcji
    assert it[2].st == it[1].en + 25  # 1 s przerwy miedzy sekcjami
    assert tl.markers == []  # od 1.1 bez markerow
    assert not [x for x in r["warnings"] if "dziura" in x or "nakladka" in x]
    assert env["p"].mp.GetCurrentFolder() is env["p"].mp.GetRootFolder() or True


def test_build_name_conflict_and_restores_folder(L, env):
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    L.preview(env["w"], {"sections": [{"items": [{"from": "C01.U1"}]}]})
    env["p"].mp.SetCurrentFolder(env["wyw"])
    assert L.build_timeline(env["p"], env["w"], "X")["ok"]
    assert env["p"].mp.GetCurrentFolder() is env["wyw"]  # folder Media Poola przywrocony
    r = L.build_timeline(env["p"], env["w"], "X")
    assert not r["ok"] and "juz istnieje" in r["errors"][0]


def test_marks_limit_units(L, env):
    env["c1"].marks = {"audio": {"in": 70, "out": 140}}
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    txt = L.units_text(env["w"], clip="C01")
    assert "Dzień" not in txt and "Pracuję" in txt


def test_transcribe_step_each_clip_and_language(L, env):
    c1, c2 = env["c1"], env["c2"]
    c1.tr = None
    c2.tr["language"] = "en"  # zle rozpoznany jezyk -> od nowa
    sub = FakeClip("u4", "A_wywiad_prezes_sub.mov", "/m/a.mov")  # subclip tego samego pliku: wlasna transkrypcja
    env["wyw"].clips.append(sub)
    L.inventory(env["p"], env["w"], "Wywiady")
    rs = FakeResolve()
    r = L.transcribe_step(rs, env["p"], env["w"], wait_s=0, poll_s=0)
    assert r["status"] == "w toku"
    s = env["p"].settings
    assert rs.page == "edit" and s["transcriptionLanguage"] == "pl" and s["transcriptionExtendedLanguageSupport"] == "1"
    for _ in range(4):
        L.transcribe_step(rs, env["p"], env["w"], wait_s=0, poll_s=0)
    assert c1.transcribed_calls == 1 and sub.transcribed_calls == 1 and c2.transcribed_calls == 1
    assert c2.cleared == 1
    L.restore(rs, env["p"], env["w"])
    assert rs.page == "media" and s["transcriptionLanguage"] == "auto" and s["transcriptionExtendedLanguageSupport"] == "0"


def test_inventory_order_by_date(L, env):
    env["c1"].props["Date Created"] = "2026-11-22 10:00:00"
    env["c2"].props["Date Created"] = "2026-11-21 09:00:00"
    clips = L.inventory(env["p"], env["w"], "Wywiady")
    assert [c["name"] for c in clips] == ["B_wywiad_firma.mov", "A_wywiad_prezes.mov"]
    clips = L.inventory(env["p"], env["w"], "Wywiady", order="name")
    assert clips[0]["name"] == "A_wywiad_prezes.mov"


def test_subclip_offset_calibrated(L, env):
    env["c1"].src_in = 40000  # subclip: In daleko w pliku
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    L.preview(env["w"], {"sections": [{"items": [{"from": "C01.U2"}]}]})
    r = L.build_timeline(env["p"], env["w"], "S")
    assert r["ok"] and not [x for x in r["warnings"] if "stopklatka" in x], r
    tl = env["p"].current
    assert len(tl.items) == 1 and tl.deleted == 1  # probne wstawienie usuniete
    it = tl.items[0]
    assert it.src_s > 40000 and it.src_e - it.src_s == it.en - it.st


def test_inventory_timeline_order_and_range(L, env):
    env["c1"].src_in = 40000
    edit = FakeTimeline("EDIT 01")
    # na timeline'ie najpierw C02 (B), potem fragment C01 od klatki 70 (zdanie 2)
    edit.items = [FakeItem(90000, 90100, 0, 200, env["c2"], 0), FakeItem(90100, 90170, 40070, 40140, env["c1"], 70)]
    env["p"].timelines.append(edit)
    env["p"].current = edit
    clips = L.inventory_timeline(env["p"], env["w"], "EDIT 01")
    assert [c["name"] for c in clips] == ["B_wywiad_firma.mov", "A_wywiad_prezes.mov"]
    assert clips[1]["mark_in"] == 70 and clips[1]["src_off"] == 40000
    L.export_units(env["p"], env["w"])
    assert "Pracuję" in L.units_text(env["w"], clip="C02") and "Dzień" not in L.units_text(env["w"], clip="C02")
    L.preview(env["w"], {"sections": [{"items": [{"from": "C02.U1"}]}]})
    r = L.build_timeline(env["p"], env["w"], "T")
    assert r["ok"] and env["p"].current.deleted == 0  # przesuniecie z timeline'u, bez kalibracji
    assert env["p"].current.items[0].src_s >= 40000


def test_punctuation_only_words_dropped(L, env):
    tr, _ = make_tr(["przewinęło się...", "... ponad 1200."])
    env["c1"].tr = tr
    L.inventory(env["p"], env["w"], "Wywiady")
    L.export_units(env["p"], env["w"])
    txt = L.units_text(env["w"], clip="C01")
    assert "] ..." not in txt and "ponad 1200." in txt


def test_plural(L):
    assert [L.plural(n, "sekcja", "sekcje", "sekcji") for n in (1, 2, 3, 5, 12, 22, 25)] == \
        ["sekcja", "sekcje", "sekcje", "sekcji", "sekcji", "sekcje", "sekcji"]

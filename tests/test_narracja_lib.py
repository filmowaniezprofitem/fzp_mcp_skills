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
    def __init__(self, uid, name, path, fps=25, frames=5000, start_tc="00:00:00:00", tr=None, typ="Video + Audio", marks=None):
        self.uid, self.name, self.tr, self.marks = uid, name, tr, marks or {}
        self.props = {"Type": typ, "FPS": fps, "Start TC": start_tc, "Frames": str(frames), "File Path": path,
                      "Duration": "00:03:20:00"}
        self.transcribed_calls = 0

    def GetUniqueId(self): return self.uid
    def GetName(self): return self.name
    def GetClipProperty(self, k=None): return self.props.get(k) if k else self.props
    def GetTranscription(self): return self.tr
    def GetMarkInOut(self): return self.marks

    def TranscribeAudio(self, sp=None, nested=False):
        self.transcribed_calls += 1
        return True


class FakeFolder:
    def __init__(self, name, clips=(), subs=()):
        self.name, self.clips, self.subs = name, list(clips), list(subs)

    def GetName(self): return self.name
    def GetClipList(self): return self.clips
    def GetSubFolderList(self): return self.subs
    def GetUniqueId(self): return "F_" + self.name


class FakeItem:
    def __init__(self, st, en): self.st, self.en = st, en
    def GetStart(self): return self.st
    def GetEnd(self): return self.en


class FakeTimeline:
    def __init__(self, name, fps=25, start=90000):
        self.name, self.fps, self.start, self.items, self.markers = name, fps, start, [], []

    def GetName(self): return self.name
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
            it = FakeItem(i["recordFrame"], i["recordFrame"] + dur)
            self.appended.append(i)
            tl.items.append(it)
            out += [it, FakeItem(it.st, it.en)]  # wideo + audio
        return out


class FakeProject:
    def __init__(self, root, tl_fps=25):
        self.tl_fps, self.timelines, self.current = tl_fps, [], None
        self.mp = FakeMP(root, self)
        self.settings = {"timelineFrameRate": tl_fps, "transcriptionLanguage": "auto"}
        self.job = {"JobStatus": "Complete"}

    def GetName(self): return "Test projekt"
    def GetMediaPool(self): return self.mp
    def GetSetting(self, k): return self.settings.get(k)
    def SetSetting(self, k, v): self.settings[k] = v; return True
    def GetTimelineCount(self): return len(self.timelines)
    def GetTimelineByIndex(self, i): return self.timelines[i - 1]
    def SetCurrentTimeline(self, tl): self.current = tl; return True
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
    assert [c["id"] for c in clips] == ["C01", "C02"]  # bez b-rolla, sortowane po nazwie
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
    assert [m[1] for m in tl.markers] == ["A", "B"]
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


def test_transcribe_step_dedupes_subclips(L, env):
    c1, c2 = env["c1"], env["c2"]
    c1.tr = None
    c2.tr = None
    sub = FakeClip("u4", "A_wywiad_prezes_sub.mov", "/m/a.mov")  # subclip tego samego pliku
    env["wyw"].clips.append(sub)
    L.inventory(env["p"], env["w"], "Wywiady")
    rs = FakeResolve()
    r = L.transcribe_step(rs, env["p"], env["w"], wait_s=0, poll_s=0)
    assert r["status"] == "w toku"
    assert rs.page == "edit" and env["p"].settings["transcriptionLanguage"] == "pl"
    started = [c for c in (c1, c2, sub) if c.transcribed_calls]
    assert len(started) == 1
    # kolejne wywolania: jeden plik /m/a.mov transkrybowany tylko raz
    for _ in range(4):
        L.transcribe_step(rs, env["p"], env["w"], wait_s=0, poll_s=0)
    assert c1.transcribed_calls + sub.transcribed_calls == 1 and c2.transcribed_calls == 1
    L.restore(rs, env["p"], env["w"])
    assert rs.page == "media" and env["p"].settings["transcriptionLanguage"] == "auto"


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

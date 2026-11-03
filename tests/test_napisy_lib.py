"""Testy biblioteki napisy_lib bez DaVinci Resolve (czyste funkcje + atrapy API)."""
import importlib.util
import json
import os
import re

import pytest

LIB = os.path.join(os.path.dirname(__file__), "..", "skills", "fzp-napisy-z-timeline", "scripts", "napisy_lib.py")


@pytest.fixture()
def L():
    spec = importlib.util.spec_from_file_location("napisy_lib", LIB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------ timecode
@pytest.mark.parametrize("fps", [24, 25, 30, 50, 60, 24000 / 1001])
def test_tc_roundtrip_ndf(L, fps):
    for fr in (0, 1, 59, 1799, 1800, 17982, 107892, 215999):
        assert L.tc2f(L.f2tc(fr, fps, df=False), fps) == fr


@pytest.mark.parametrize("fps", [30000 / 1001, 60000 / 1001])
def test_tc_roundtrip_df(L, fps):
    for fr in range(0, 300000, 37):
        tc = L.f2tc(fr, fps, df=True)
        assert ";" in tc
        assert L.tc2f(tc, fps) == fr, (fr, tc)


def test_df_known_values(L):
    f = 30000 / 1001
    assert L.f2tc(1799, f, df=True) == "00:00:59;29"
    assert L.f2tc(1800, f, df=True) == "00:01:00;02"
    assert L.f2tc(17982, f, df=True) == "00:10:00;00"
    assert L.f2tc(107892, f, df=True) == "01:00:00;00"


def test_global_df_flag(L):
    f = 30000 / 1001
    L.TC_DF = True
    assert L.f2tc(1800, f) == "00:01:00;02"
    L.TC_DF = False
    assert L.f2tc(1800, f) == "00:01:00:00"


def test_f2srt(L):
    assert L.f2srt(25, 25) == "00:00:01,000"
    assert L.f2srt(90000, 25) == "01:00:00,000"
    assert L.f2srt(24, 24000 / 1001) == "00:00:01,001"


# ------------------------------------------------------------------ tekst
def W(t, s, e, sp="S1"):
    return dict(t=t, s=s, e=e, sp=sp)


def test_default_units_sentence_and_speaker(L):
    ws = [W("Dzień", 0, 10), W("dobry.", 10, 20), W("Jak", 25, 30), W("się", 30, 35), W("masz?", 35, 45),
          W("Dobrze.", 50, 60, "S2")]
    u = L.default_units(ws, 25, L.PROFILES["montazowy"])
    assert u == [[0, 1], [2, 3, 4], [5]]


def test_default_units_soft_split_on_relative(L):
    ws = [W("To", 0, 5), W("jest", 5, 10), W("film,", 10, 20), W("który", 20, 25), W("zrobiłem.", 25, 40)]
    u = L.default_units(ws, 25, L.PROFILES["montazowy"])
    assert u == [[0, 1, 2], [3, 4]]


def test_abbreviation_not_sentence_end(L):
    assert not L._sentence_end("np.")
    assert L._sentence_end("koniec.")
    assert L._sentence_end("serio?!")


def test_apply_plan(L):
    ws = [W("nad", 0, 5), W("odra", 5, 10), W("płynie.", 10, 20), W("Potem", 30, 35), W("cisza.", 35, 45),
          W("szum", 50, 55)]
    units = [[0, 1, 2], [3, 4], [5]]
    plan = {"edits": [{"u": 1, "old": "odra", "new": "Odrą"}, {"u": 2, "old": "cisza.", "new": "była cisza."}],
            "split": [{"u": 1, "before": "płynie."}], "drop": [3], "speakers": {"2": "B"}}
    out, err = L.apply_plan(ws, units, plan)
    assert err == []
    assert [[w["t"] for w in u] for u in out] == [["nad", "Odrą"], ["płynie."], ["Potem", "była", "cisza."]]
    assert out[2][0]["sp"] == "B"
    # proporcjonalne czasy przy zmianie liczby slow mieszcza sie w oryginale
    assert out[2][1]["s"] >= 35 and out[2][2]["e"] == 45


def test_apply_plan_join_and_errors(L):
    ws = [W("Raz", 0, 5), W("dwa", 5, 10), W("trzy.", 10, 20)]
    out, err = L.apply_plan(ws, [[0], [1, 2]], {"join": [1]})
    assert err == [] and len(out) == 1 and len(out[0]) == 3
    out, err = L.apply_plan(ws, [[0], [1, 2]], {"edits": [{"u": 1, "old": "nie ma", "new": "x"}]})
    assert err and "nie znaleziono" in err[0]


def test_layout_avoids_hanging_preposition(L):
    ws = "Pojechaliśmy wczoraj z całą rodziną nad samo morze do Gdańska".split()
    lines, cost = L.layout_unit(ws, 42, 2)
    assert len(lines) == 2
    assert all(L._bare(l[-1]) not in L.PREP | L.CONJ | L.ONE_LETTER for l in lines[:-1])
    assert all(len(" ".join(l)) <= 42 for l in lines)


def test_layout_impossible(L):
    assert L.layout_unit(["a" * 50], 42, 2) is None


# ------------------------------------------------------------------ pelny build bez Resolve
def make_workdir(tmp_path, L, fps=25, start_frame=90000, df=False):
    text = ("Dzień dobry, nazywam się Marcin i robię filmy. Dzisiaj pokażę wam, jak zrobić napisy. "
            "To naprawdę nie jest trudne, jeśli wiesz, od czego zacząć. Zaczynamy?").split()
    words, t = [], start_frame + 12
    for i, w in enumerate(text):
        d = 6 + len(w)
        words.append(dict(t=w, s=t, e=t + d, sp="S1" if i < 20 else "S2"))
        t += d + (20 if w.endswith(".") else 2)
    inv = dict(timeline="Test TL", fps=fps, df=df, res=[1920, 1080], orientation="poziom", layout=[42, 2],
               start_tc="01:00:00:00", start_frame=start_frame, end_frame=t + 100, audio=[], lang="pl",
               subtitle_tracks=0)
    w = str(tmp_path)
    L._dump(w, "words.json", words)
    L._dump(w, "timeline.json", dict(cuts=[start_frame + 150, start_frame + 400], inv=inv))
    return w, words


def parse_srt(path):
    blocks = open(path, encoding="utf-8").read().strip().split("\n\n")
    out = []
    for b in blocks:
        lines = b.split("\n")
        m = re.match(r"(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})$", lines[1])
        assert m, lines[1]
        v = [int(x) for x in m.groups()]
        st = ((v[0] * 60 + v[1]) * 60 + v[2]) * 1000 + v[3]
        en = ((v[4] * 60 + v[5]) * 60 + v[6]) * 1000 + v[7]
        out.append((int(lines[0]), st, en, lines[2:]))
    return out


@pytest.mark.parametrize("profile", ["montazowy", "netflix"])
def test_build_end_to_end(tmp_path, L, profile):
    w, words = make_workdir(tmp_path, L)
    print(L.prepare(w, profile))
    r = L.build(w, {}, profile)
    assert "errors" not in r
    assert r["params"]["words"] == len(words)
    assert not [x for x in r["warnings"] if "liczba slow" in x]
    subs = parse_srt(r["files"][0])
    assert [s[0] for s in subs] == list(range(1, len(subs) + 1))
    for (_, st, en, lines), nxt in zip(subs, subs[1:] + [None]):
        assert en > st
        assert len(lines) <= 2 and all(len(l) <= 42 for l in lines)
        if nxt:
            assert nxt[1] >= en
    # plik do Resolve: bezwzgledny TC (01:00:00), dla klienta: od zera
    assert subs[0][1] >= 3600 * 1000
    assert r["delivery"] and parse_srt(r["delivery"][0])[0][1] < 3600 * 1000
    assert os.path.exists(os.path.join(w, "plan.json")) and os.path.exists(os.path.join(w, "params.json"))


def test_rebuild_keeps_plan_and_overrides(tmp_path, L):
    w, words = make_workdir(tmp_path, L)
    L.prepare(w)
    r1 = L.build(w, {"edits": [{"u": 1, "old": "Marcin", "new": "Marcin Testowy"}]}, "montazowy")
    r2 = L.rebuild(w, profile="netflix", max_chars=32)
    assert r2["params"]["profile"] == "netflix" and r2["params"]["max_chars"] == 32
    assert r2["params"]["words"] == r1["params"]["words"] == len(words) + 1
    assert any("Testowy" in p for p in r2["preview"])
    for _, _, _, lines in parse_srt(r2["files"][0]):
        assert all(len(l) <= 32 for l in lines)
    assert r2["files"][0] != r1["files"][0]  # nowa wersja _v2, stara zostaje


def test_rebuild_plan_patch(tmp_path, L):
    w, _ = make_workdir(tmp_path, L)
    L.prepare(w)
    L.build(w, {"drop": [1]}, "montazowy")
    r = L.rebuild(w, plan_patch={"drop": [2]})
    assert json.load(open(os.path.join(w, "plan.json"), encoding="utf-8"))["drop"] == [1, 2]
    assert "errors" not in r


def test_build_df_preview(tmp_path, L):
    w, _ = make_workdir(tmp_path, L, fps=30000 / 1001, start_frame=107892, df=True)
    L.prepare(w)
    r = L.build(w, {}, "montazowy")
    assert all(";" in p.split(" ")[0] for p in r["preview"])


def test_build_per_speaker(tmp_path, L):
    w, _ = make_workdir(tmp_path, L)
    L.prepare(w)
    r = L.build(w, {}, "montazowy", per_speaker=True)
    assert len(r["files"]) == 2 and set(r["counts"]) == {"S1", "S2"}


# ------------------------------------------------------------------ atrapy API Resolve
class FakeResolve:
    def __init__(self, v, prod="DaVinci Resolve Studio"):
        self.v, self.prod = v, prod

    def GetVersionString(self):
        return self.v

    def GetProductName(self):
        return self.prod


def test_check_env(L):
    assert L.check_env(FakeResolve("21.1.0.12"))["ok"]
    assert L.check_env(FakeResolve("22.0"))["ok"]
    assert not L.check_env(FakeResolve("20.3.1"))["ok"]
    r = L.check_env(FakeResolve("21.1", "DaVinci Resolve"))
    assert not r["ok"] and "Studio" in r["reason"]


class FakeProject:
    def __init__(self, presets):
        self.presets = presets

    def GetRenderPresetList(self):
        return self.presets


def test_snapshot_refuses_abandoned(tmp_path, L):
    with pytest.raises(RuntimeError, match="PORZUCONY_PRZEBIEG"):
        L.snapshot(None, FakeProject([L.BACKUP_PRESET]), str(tmp_path))


def test_find_abandoned(tmp_path, L, monkeypatch):
    monkeypatch.setattr(L, "desktop_dir", lambda: str(tmp_path / "nie_ma"))
    base = tmp_path / "Napisy_X"
    for name, fin in (("a", True), ("b", False)):
        (base / name).mkdir(parents=True)
        (base / name / "state.json").write_text(json.dumps(dict(finished=fin)), encoding="utf-8")
    r = L.find_abandoned(FakeProject([L.BACKUP_PRESET]), str(base))
    assert r["preset"] is True
    assert r["workdirs"] == [str(base / "b")]


def test_new_workdir_unique(tmp_path, L):
    a = L.new_workdir(str(tmp_path), "Mój timeline: v2")
    b = L.new_workdir(str(tmp_path), "Mój timeline: v2")
    assert a != b and os.path.isdir(a) and os.path.isdir(b)
    assert ":" not in os.path.basename(a)

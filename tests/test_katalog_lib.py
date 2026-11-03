"""Testy biblioteki katalog_lib bez DaVinci Resolve (atrapy API + prawdziwy DOCX)."""
import importlib.util
import os

import pytest

from test_narracja_lib import FakeClip, FakeFolder, FakeProject, make_tr, S1, S2

LIB = os.path.join(os.path.dirname(__file__), "..", "skills", "fzp-katalog-wypowiedzi", "scripts", "katalog_lib.py")


@pytest.fixture()
def K():
    spec = importlib.util.spec_from_file_location("katalog_lib", LIB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class MClip(FakeClip):
    """Klip z metadanymi i markerami."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.md, self.markers = {}, {}

    def GetMetadata(self): return dict(self.md)
    def SetMetadata(self, d): self.md.update(d); return True
    def GetMarkers(self): return dict(self.markers)

    def AddMarker(self, fr, color, name, note, dur, custom=None):
        if fr in self.markers:
            return False
        self.markers[fr] = dict(color=color, name=name, note=note, duration=dur, customData=custom or "")
        return True

    def DeleteMarkerAtFrame(self, fr): return self.markers.pop(fr, None) is not None


class AFolder(FakeFolder):
    def AnalyzeForIntellisearch(self, faces, better):
        self.analyzed = (faces, better)
        return True


@pytest.fixture()
def env(K, tmp_path):
    tr1, _ = make_tr(S1)
    tr2, _ = make_tr(S2, fps=50, base="01:00:00:00", sp="Speaker 2")
    c1 = MClip("u1", "A_wywiad_prezes.mov", "/m/a.mov", tr=tr1)
    c2 = MClip("u2", "B_wywiad_firma.mov", "/m/b.mov", fps=50, start_tc="01:00:00:00", tr=tr2)
    c1.markers[5] = dict(color="Red", name="moj marker", note="", duration=1, customData="")  # cudzy marker zostaje
    c2.md = {"Description": "Opis montazysty", "Keywords": "wazne"}
    wyw = AFolder("Wywiady", [c1, c2])
    p = FakeProject(FakeFolder("Master", [], [wyw]))
    w = str(tmp_path / "w")
    os.makedirs(w)
    K.inventory(p, w, "Wywiady")
    K.export_units(p, w)
    return dict(p=p, w=w, c1=c1, c2=c2, wyw=wyw, tmp=tmp_path)


CAT = {
    "title": "Katalog: Test",
    "subtitle": "Materiał: 2 wywiady",
    "people": {"C01": {"name": "Jan Kowalski", "role": "prezes strefy", "summary": "Historia strefy i liczby."},
               "C02": {"name": "Anna Nowak", "role": "właścicielka firmy"}},
    "overview": [{"heading": "Kto wystąpił", "bullets": ["Jan Kowalski – prezes", "Anna Nowak – firma"]},
                 {"heading": "Braki względem briefu", "paragraphs": ["Brak wypowiedzi o planach na przyszłość."]}],
    "quotes": [
        {"id": "Q001", "topic": "Historia", "from": "C01.U2"},
        {"id": "Q002", "topic": "Historia", "from": "C01.U3", "start_at": "to był", "broll": "archiwalne zdjęcia"},
        {"id": "Q003", "topic": "Dziś", "from": "C01.U4", "broll": "hala, pracownicy"},
        {"id": "Q004", "topic": "Dziś", "from": "C02.U2"},
    ],
}


def test_apply_catalog_metadata_markers_docx(K, env):
    path = str(env["tmp"] / "kat.docx")
    r = K.apply_catalog(env["p"], env["w"], CAT, docx_path=path, intellisearch=True)
    assert r["ok"], r
    assert r["quotes"] == 4 and r["markers"] == 4 and os.path.exists(path)
    c1, c2 = env["c1"], env["c2"]
    assert c1.md["Description"].startswith("Jan Kowalski – prezes strefy. Historia")
    assert "osoba:Jan Kowalski" in c1.md["Keywords"] and "temat:Historia" in c1.md["Keywords"]
    assert c2.md["Description"] == "Opis montazysty"  # cudzy opis nie nadpisany
    assert c2.md["Keywords"].startswith("wazne,") and "osoba:Anna Nowak" in c2.md["Keywords"]
    assert r["metadata_kept"] == ["B_wywiad_firma.mov"]
    ours = [m for m in c1.markers.values() if m["customData"].startswith("fzp-katalog:")]
    assert len(ours) == 3 and 5 in c1.markers
    assert env["wyw"].analyzed == (True, False) and r["intellisearch"]


def test_rerun_replaces_only_own_markers(K, env):
    K.apply_catalog(env["p"], env["w"], CAT, docx_path=str(env["tmp"] / "a.docx"))
    cat2 = dict(CAT, quotes=CAT["quotes"][:2])
    r = K.apply_catalog(env["p"], env["w"], cat2, docx_path=str(env["tmp"] / "b.docx"))
    ours = [m for m in env["c1"].markers.values() if m["customData"].startswith("fzp-katalog:")]
    assert r["markers"] == 2 and len(ours) == 2 and 5 in env["c1"].markers


def test_apply_catalog_errors(K, env):
    bad = dict(CAT, quotes=[{"id": "Q1", "from": "C01.U1"}, {"id": "Q1", "from": "C01.U2"}, {"id": "Q3", "from": "C09.U1"}])
    r = K.apply_catalog(env["p"], env["w"], bad, docx_path=str(env["tmp"] / "x.docx"))
    assert not r["ok"] and any("C09" in e for e in r["errors"])


def test_docx_opens_in_python_docx(K, env):
    docx = pytest.importorskip("docx")
    path = str(env["tmp"] / "kat.docx")
    K.apply_catalog(env["p"], env["w"], CAT, docx_path=path)
    d = docx.Document(path)
    heads = [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]
    assert "Wybrane cytaty" in heads and "Kto wystąpił" in heads
    assert len(d.tables) == 4  # 2 tematy + aneks dla 2 klipow
    assert [c.text for c in d.tables[0].rows[0].cells][:4] == ["Kol.", "ID", "Kto", "Klip / TC"]
    sec = d.sections[0]
    assert sec.page_width > sec.page_height  # A4 poziomo


def fill(path, out, picks, strike=None, notes=None):
    """Symulacja reżysera w Wordzie: wpisuje numery w Kol., skreśla słowo, dopisuje uwagę."""
    import docx
    d = docx.Document(path)
    for t in d.tables:
        hdr = [c.text for c in t.rows[0].cells]
        for row in t.rows[1:]:
            rid = row.cells[hdr.index("ID")].text
            if rid in picks:
                row.cells[0].text = str(picks[rid])
            if notes and rid in notes:
                row.cells[hdr.index("Uwagi")].text = notes[rid]
            if strike and rid in strike:
                cell = row.cells[hdr.index("Cytat") if "Cytat" in hdr else hdr.index("Tekst")]
                p = cell.paragraphs[0]
                full = p.text
                word = strike[rid]
                a, b = full.split(word, 1)
                for r in list(p.runs):
                    r._element.getparent().remove(r._element)
                p.add_run(a)
                p.add_run(word).font.strike = True
                p.add_run(b)
    d.save(out)


def test_roundtrip_selection(K, env):
    pytest.importorskip("docx")
    path, out = str(env["tmp"] / "kat.docx"), str(env["tmp"] / "kat_rezyser.docx")
    K.apply_catalog(env["p"], env["w"], CAT, docx_path=path)
    fill(path, out, {"Q003": 2, "Q001": 1, "C02.U1": "2.5", "Q004": 3},
         strike={"Q003": "Dzisiaj "}, notes={"Q004": "tylko pierwsze zdanie"})
    sel = K.selection_from_docx(out)
    assert sel["errors"] == []
    assert [i["id"] for i in sel["items"]] == ["Q001", "Q003", "C02.U1", "Q004"]
    q3 = sel["items"][1]
    assert q3["text"].startswith("mamy dwadzieścia")  # skreślone słowo pominięte
    assert q3["clip"] == "A_wywiad_prezes.mov" and q3["tc_in"] < q3["tc_out"]
    assert sel["items"][3]["notes"] == "tylko pierwsze zdanie"
    assert sel["items"][2]["clip"] == "B_wywiad_firma.mov" and sel["items"][2]["tc_in"].startswith("01:")


def test_build_from_docx_items(K, env):
    pytest.importorskip("docx")
    path, out = str(env["tmp"] / "kat.docx"), str(env["tmp"] / "kat_rezyser.docx")
    K.apply_catalog(env["p"], env["w"], CAT, docx_path=path)
    fill(path, out, {"Q001": 1, "Q003": 2, "Q004": 3})
    items = K.selection_from_docx(out)["items"]
    items[1]["start_at"] = "mamy"  # model: skreślenie -> start_at
    for it in items[:2]:
        it["section"] = "Historia i dziś"
    items[2]["section"] = "Firmy"
    pv = K.preview_items(env["p"], items)
    assert not pv["errors"] and pv["items"] == 3 and "### Firmy" in pv["text"]
    assert "„mamy dwadzieścia" in pv["text"]
    r = K.build_from_items(env["p"], "Rezyser e01", items, gap_s=1.0)
    assert r["ok"], r
    tl = env["p"].current
    assert tl.name == "Rezyser e01" and r["clips"] == 3
    assert [m[1] for m in tl.markers] == ["Historia i dziś", "Firmy"]
    assert not [x for x in r["warnings"] if "dziura" in x or "nakladka" in x]


def test_selection_errors(K, tmp_path):
    w = str(tmp_path / "pusty.docx")
    spec = importlib.util.spec_from_file_location("k2", LIB)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.write_docx(w, [("table", ["Kol.", "ID", "Klip / TC", "Cytat"], [["", "Q1", "klip\n00:00:01:00–00:00:02:00", "x"]],
                      [700, 700, 2000, 4000], (0,))])
    assert "nie znaleziono" in m.selection_from_docx(w)["errors"][0]
    m.write_docx(w, [("table", ["Kol.", "ID", "Klip / TC", "Cytat"], [["1", "Q1", "klip bez tc", "x"], ["2", "Q2", "k\n00:00:01:00–00:00:02:00", "y"],
                                                                     ["2", "Q3", "k\n00:00:03:00–00:00:04:00", "z"]], [700, 700, 2000, 4000], (0,))])
    s = m.selection_from_docx(w)
    assert any("Q1" in e for e in s["errors"]) and any("ten sam numer" in x for x in s["warnings"])
    assert [i["id"] for i in s["items"]] == ["Q2", "Q3"]

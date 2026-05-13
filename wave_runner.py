"""Wave runner — orchestrates research waves with configurable agent pipelines."""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict

from tools.knowledge_base import KnowledgeBase
from tools.wiki_builder import WikiBuilder
from agents.historiker import Historiker
from agents.bildredakteur import Bildredakteur
from agents.journalist import Journalist
from agents.archivar import Archivar
from agents.verifier import Verifier
from agents.strict_verifier import StrictVerifier
from agents.redakteur import Redakteur
from config import WAVES_DIR, CATEGORIES

# ─── Seed topics for Wave 0 (pure model knowledge) ───────────────────────────
WAVE_0_SEEDS: Dict[str, List[str]] = {
    "agencies": [
        "J. Walter Thompson (JWT) — die älteste Werbeagentur",
        "Doyle Dane Bernbach (DDB) — die Creative Revolution",
        "Leo Burnett Company — Chicago School of Advertising",
        "Ogilvy & Mather — David Ogilvys Agenturprinzipien",
        "BBDO — Batten Barton Durstine & Osborn",
        "Young & Rubicam — Forschung und Kreativität",
        "Ted Bates & Company — die USP-Agentur",
        "Saatchi & Saatchi — Thatcherisierung der Werbung",
        "TBWA — Disruption als Strategie",
        "Springer & Jacoby Hamburg",
        "GGK — Grey Group Kommunikation Deutschland",
        "BBDO Germany / Düsseldorf",
    ],
    "people": [
        "Bill Bernbach — Vater der Kreativen Revolution",
        "David Ogilvy — der Werbe-Guru",
        "Leo Burnett — der Chicagoer Geschichtenerzähler",
        "Mary Wells Lawrence — erste weibliche Agentur-CEO",
        "Rosser Reeves — USP und Hard Sell",
        "Helmut Krone — Art Director und Typograf",
        "Howard Gossage — das Gewissen der Werbung",
        "George Lois — Art Director und Provokateur",
    ],
    "eras": [
        "Die Schaufenster-Ära der Werbung (1880–1929)",
        "Werbung im Zweiten Weltkrieg — Propaganda und Konsumwerbung",
        "Die Mad Men Ära (1950–1970) — Goldenes Zeitalter der Werbung",
        "Die Kreative Revolution der 1960er Jahre",
        "Werbung in den 1970ern — Ölkrise und gesellschaftlicher Wandel",
        "Desktop Publishing und die digitale Wende (1984–1995)",
    ],
    "work": [
        "Think Small — VW Käfer Kampagne von DDB 1959",
        "Marlboro Man — Leo Burnetts ikonischste Kampagne",
        "Avis We Try Harder — die Underdog-Strategie",
        "Alka Seltzer — How do you spell relief",
        "Der Pitch — Geschichte und Ablauf eines Werbepitches",
        "Die Jahresetat-Präsentation — Agenturalltag",
    ],
    "life": [
        "Tagesablauf in einer Werbeagentur der 1960er Jahre",
        "Die Rolle des Account Managers in der klassischen Agentur",
        "Art Director und Copywriter — das kreative Team",
        "Der Creative Director — Entstehung der Rolle",
        "Honorarmodelle — 15%-Provision vs. Fee-System",
        "Agentur-Hierarchien und Organigramme (1950–1980)",
    ],
    "technology": [
        "Der Zeichentisch und seine Werkzeuge in der Werbeagentur",
        "Typosatz, Repro-Kamera und Druckvorstufe",
        "Fotoatelier und Fotostudio in der Agentur",
        "Erste Computer in der Werbeagentur — Mac und PageMaker 1985",
        "Storyboard und Filmproduktion für TV-Werbung",
    ],
    "philosophy": [
        "Die Unique Selling Proposition (USP) — Rosser Reeves",
        "Brand Image — David Ogilvys Markenphilosophie",
        "Der Schweizer Stil und seine Einflüsse auf die Werbegrafik",
        "Konzeptdenken vs. Hard Sell — philosophischer Streit",
        "Feminist Advertising — Werbung und Frauenbewegung",
    ],
    "scandals": [
        "Cigarette Advertising — der Fall der Tabakwerbung",
        "Subliminal Advertising — die Unterschwelligkeits-Kontroverse",
        "Benetton und Oliviero Toscani — Schockwerbung",
        "Die Plagiats-Affären der Werbebranche",
    ],
    "visuals": [
        "Visuelles aus dem Agenturalltag — Büros und Studios der 1960er",
        "Historische Anzeigen-Reinzeichnungen und Paste-up Technik",
        "Präsentationsräume und Pitch-Material-Ästhetik",
        "Storyboards und Skizzen aus Werbeagenturen",
    ],
}

# ─── Wave 1: Gap topics + web-enriched deep dives ────────────────────────────
WAVE_1_TOPICS: Dict[str, List[str]] = {
    "agencies": [
        "McCann Erickson — Internationale Agenturgeschichte",
        "Grey Advertising — die New Yorker Agentur",
        "Foote Cone & Belding (FCB) — Geschichte",
        "Lürzer & Conrad — Europäische Kreativ-Agentur",
        "Publicis Groupe — französische Werbeagentur mit globaler Präsenz",
        "Wiedemann & Berg — deutsche Agentur mit internationalem Erfolg",
        "Chiat/Day — Apple 1984 und Think Different",
        "AMV BBDO London — Abbott Mead Vickers",
    ],
    "people": [
        "Lee Clow — Apple-Kreativdirektor und TBWA",
        "Neil French — britischer Kreativdirektor und Werbetexter",
        "Helmut Krone — Typograf und Art Director bei DDB",
        "Mary Wells Lawrence — erste weibliche Werbeagentur-Chefin",
        "Paul Arden — Kreativdirektor bei Saatchi & Saatchi",
        "Dan Wieden — Just Do It und Wieden+Kennedy",
    ],
    "life": [
        "Tagesablauf und Arbeitsalltag in einer Werbeagentur der 1960er Jahre",
        "Arbeitsalltag in einer Werbeagentur der 1980er Jahre",
        "Agentur-Hierarchien und Organigramme — von der Boutique zum Netzwerk",
        "Freelancer und freie Kreative in der Werbebranche",
        "Agenturkultur — Partys, Rituale und Firmenmythen",
        "Das Briefing — wie Aufträge in Agenturen ankommen und bearbeitet werden",
    ],
    "technology": [
        "Zeichentisch, Rapidograph und Rubbelfolie — klassische Werkzeuge",
        "Repro-Kamera und Lichtsatz — Druckvorstufe vor dem Computer",
        "Fotoatelier in der Werbeagentur — Studio, Beleuchtung, Kameras",
        "Apple Macintosh und Desktop Publishing — die Revolution von 1984",
    ],
    "philosophy": [
        "Account Planning — Stephen King und der strategische Planer",
        "Die Debatte um Ethik in der Werbung",
        "Konzeptdenken vs. Hard Sell — philosophischer Streit in der Branche",
        "Der Schweizer Stil — Basel, Zürich und internationaler Grafik-Stil",
    ],
    "scandals": [
        "Werbeskandale der 1990er Jahre — Kontroversen und Rückrufe",
        "Sexismus in der Werbung — historische Debatte und Kritik",
        "Greenwashing und irreführende Werbung — Geschichte",
    ],
    "visuals": [
        "Bildquellen: Agenturalltag 1950–1970 — Archive und Fundstellen",
        "Bildquellen: Klassische Druckanzeigen und Layout-Prozess",
        "Bildquellen: Porträts der Werbebranche — Fotografen und Archive",
        "Bildquellen: Cannes Lions und Werbefestival-Dokumentation",
        "Bildquellen: D&AD Annual und Communication Arts Archive",
    ],
    "eras": [
        "Die digitale Revolution in der Werbeindustrie 1995–2005",
        "Die Ära der Werbenetze und Holdinggesellschaften 1980–2000",
        "Cannes Lions — Geschichte des Werbefestivals",
    ],
    "work": [
        "Die Rolle des Media-Planers in der Werbeagentur",
        "Werbefilm-Produktion — von der Idee zum TV-Spot",
        "Das Art Directors Annual — Geschichte und Bedeutung",
        "Cannes-Gewinner und ihre Entstehungsgeschichten",
    ],
}


# ─── Wave 3: Anthropologie des Agenturlebens ─────────────────────────────────
WAVE_3_TOPICS: Dict[str, List[str]] = {

    "life": [
        # Codes & Kleiderordnung
        "Dresscode in Werbeagenturen — schwarzer Rollkragen, Nickelbrille und die kreative Uniform",
        "Account Manager vs. Kreative — die ewige Feindschaft zwischen Suits und Jeans",
        "Bürodesign als Markensignal — wie Werbeagenturen ihre Räume für Kunden inszenierten",
        # Macht & Hierarchie
        "Praktikanten-Ausbeutung in Werbeagenturen — unbezahlte Arbeit als Normalzustand",
        "Abwerben von Kreativen und Kunden — Headhunter und Wechselkultur in der Werbebranche",
        "Kunden mitnehmen beim Agenturwechsel — das Etat-Mitnahme-Phänomen",
        "Agentur-Spin-offs und Gründungsmythen — wenn Kreative die Mutterfirma verlassen",
        "Großkunden-Macht — wenn der Client mehr zu sagen hat als der Creative Director",
        # Status & Wettbewerb
        "Agentur-Rankings in Fachzeitschriften — W&V, Horizont, Campaign, Advertising Age",
        "Der Kreativdirektor des Jahres — Ego, Status und Wettbewerb in der Werbebranche",
        "Das Portfolio (Book) — wie Kreative Jobs bekommen, zeigen und bewacht werden",
        "Cannes als Klassentreffen — was jenseits der Awards in Cannes wirklich passiert",
        "Die Fachpresse als Machtinstrument — wer in W&V und Horizont erscheint",
        # Alltag & Ritual
        "Pitch-Kultur und der All-nighter — Überstunden, Romantik und Erschöpfung",
        "Kundenpflege und Kundenunterhaltung — Dinner, Reisen, Gefälligkeiten",
        "Das Kreativ-Briefing — Ritual, Missverständnis und Neuverhandlung",
    ],

    "scandals": [
        "Kokain und Drogenkultur in Werbeagenturen 1970–1995 — dokumentiert und strukturell",
        "Der Drei-Martini-Lunch — Alkohol als professionelle Agenturkultur",
        "Scam Ads — Arbeiten die nur für Awards existieren und nie geschaltet wurden",
        "Sexismus in Werbeagenturen — Machtmissbrauch, Casting-Couch und strukturelle Ungleichheit",
        "Neil French Sexismus-Skandal 2005 — Rücktritt eines Weltklasse-Kreativedirektors",
        "JWT-Finanzskandal 1982 — CEO John Peters und der Rechnungsbetrug",
        "Award-Show-Politik — Jury-Schiebung, gegenseitige Gefälligkeiten, gekaufte Preise",
        "Burnout und psychische Gesundheit in der Werbebranche — der bezahlte Preis",
    ],

    "work": [
        "Scribble, Reinzeichnung und Repro — der physische Weg einer Anzeige von Idee bis Druck",
        "Shooting-Kultur in der Werbefotografie — Fotografen, Locations, Budgets, Reisen",
        "Jingles und Werbemusik — Komposition, Produktion, Ohrwürmer als Strategie",
        "Voice-over und Radiowerbung — eine eigene kreative Disziplin",
        "D&AD Yellow Pencil und Black Pencil — die Währung des kreativen Prestiges",
        "Scribble und Ideen-Skizzen — Handwerk der Konzeptentwicklung",
        "Storyboard-Kultur — vom Scribble zum Filmset",
    ],

    "people": [
        "Amir Kassaei — DDB Germany und der Kreative mit den meisten Cannes-Löwen",
        "Jean-Marie Dru — TBWA und das Disruption-Konzept",
        "Michael Conrad — Leo Burnett Germany, D&AD-Präsident und Grandseigneur",
        "Phyllis Robinson — erste weibliche Creative Directorin bei DDB",
        "Erik Spiekermann — Typografie, MetaDesign und der Schriftgestalter als Marke",
        "Helmut Pantke — GGK und die deutsche Agenturlandschaft",
    ],

    "agencies": [
        "Serviceplan München — gegründet 1970, Europas größte unabhängige Agentur",
        "Jung von Matt — Hamburg 1991, Gründungsmythos und deutsche Kreativrevolution",
        "Wieden+Kennedy — Dan Wieden, Nike und das Modell der unabhängigen Agentur",
        "Chiat/Day — Apple 1984, Think Different und Jay Chiats Persönlichkeit",
        "Fallon McElligott — Minneapolis, Mittelamerika und die Gegenbewegung zu Madison Ave.",
        "Grabarz & Partner — Hamburg und die erste Generation nach der Wiedervereinigung",
        "Heye & Partner München — DDB-Tochter und die Münchner Agenturszene",
        "FCO Univas und die britische Agenturszene der 1980er Jahre",
        "AMV BBDO London — Abbott Mead Vickers und der britische Kreativboom",
    ],

    "technology": [
        "Leuchtkasten, Lineal und Rapidograph — das analoge Handwerkszeug des Art Directors",
        "Paste-up und Klebeumbruch — die Druckvorstufe vor Desktop Publishing",
        "Testmarketing und Fokusgruppen-Technik — wie Werbung vor dem Launch getestet wurde",
    ],

    "philosophy": [
        "Die Mythologie des kreativen Genies — Einzelkämpfer-Mythos vs. Teamrealität",
        "Die Idee der Werbeagentur als Gesamtkunstwerk — totale Markenführung",
        "Kreative Freiheit vs. Kundenbrief — der ewige Grundkonflikt der Branche",
        "Werbung als Spiegel der Gesellschaft — Zeitgeist und kulturelle Verantwortung",
    ],

    "visuals": [
        "Bildquellen: Kreative Uniform und Dresscode — Fotomaterial aus Agenturen",
        "Bildquellen: Behind-the-Scenes Werbeshootings — Fotografen und Archive",
        "Bildquellen: Agentur-Innenräume und Bürodesign 1960–1990",
        "Bildquellen: Scribbles, Skizzen und Rohkonzepte aus Archiven",
        "Bildquellen: Award-Shows und Branchenveranstaltungen historisch",
    ],

    "eras": [
        "Die Münchner Werbeszene — Bayern als zweites Zentrum neben Hamburg und Düsseldorf",
        "Die Hamburger Werbeszene — von GGK über Springer & Jacoby zu Jung von Matt",
        "Werbebranche in der Schweiz — Wirz, Ruf Lanz, Advico und Helvetica",
        "London als kreatives Zentrum — Swinging Sixties bis Cool Britannia",
    ],
}


class WaveRunner:
    def __init__(self, kb: Optional[KnowledgeBase] = None):
        self.kb = kb or KnowledgeBase()
        self.historiker = Historiker(self.kb)
        self.bildredakteur = Bildredakteur(self.kb)
        self.journalist = Journalist(self.kb)
        self.archivar = Archivar(self.kb)
        self.verifier = Verifier(self.kb)
        self.strict_verifier = StrictVerifier(self.kb)
        self.redakteur = Redakteur(self.kb)
        self.wiki = WikiBuilder(self.kb)

    def run_wave_0(self, dry_run: bool = False) -> Dict:
        """Bootstrap wave: research all seed topics from model knowledge only."""
        wave = 0
        print(f"\n{'='*60}")
        print(f"WELLE 0 — Bootstrap (Modell-Wissen)")
        print(f"{'='*60}\n")

        results = {"wave": 0, "topics_done": [], "errors": []}
        total = sum(len(v) for v in WAVE_0_SEEDS.values())
        done = 0

        for category, topics in WAVE_0_SEEDS.items():
            print(f"\n[{category.upper()}]")
            for topic in topics:
                if self.kb.exists(category, topic):
                    print(f"  [skip] {topic} (bereits vorhanden)")
                    done += 1
                    results["topics_done"].append(topic)
                    continue
                if dry_run:
                    print(f"  [dry-run] {topic}")
                    done += 1
                    continue
                try:
                    self.historiker.use_web = False
                    path = self.historiker.research(topic, wave=wave)
                    if path:
                        results["topics_done"].append(topic)
                except Exception as e:
                    print(f"  [FEHLER] {topic}: {e}")
                    results["errors"].append({"topic": topic, "error": str(e)})
                done += 1
                print(f"  Progress: {done}/{total}")

        self._finalize_wave(wave, results)
        return results

    def run_wave_1(self, dry_run: bool = False) -> Dict:
        """Wave 1: gap topics with web research, category-aware routing."""
        wave = 1
        print(f"\n{'='*60}")
        print(f"WELLE 1 — Gap-Themen mit Web-Recherche")
        print(f"{'='*60}\n")

        results = {"wave": 1, "topics_done": [], "errors": []}
        self.historiker.use_web = True
        total = sum(len(v) for v in WAVE_1_TOPICS.values())
        done = 0

        for category, topics in WAVE_1_TOPICS.items():
            print(f"\n[{category.upper()}]")
            for topic in topics:
                done += 1
                # Skip if exact file already exists for this topic
                if self.kb.exists(category, topic):
                    print(f"  [skip] {topic}")
                    results["topics_done"].append(topic)
                    continue
                if dry_run:
                    print(f"  [dry-run] {topic}")
                    continue

                # Visuals category → Bildredakteur, rest → Historiker
                try:
                    if category == "visuals":
                        path = self.bildredakteur.research_visuals(topic, wave=wave)
                    else:
                        path = self.historiker.research(topic, wave=wave)
                    if path:
                        results["topics_done"].append(topic)
                except Exception as e:
                    print(f"  [FEHLER] {topic}: {e}")
                    results["errors"].append({"topic": topic, "error": str(e)})
                print(f"  Progress: {done}/{total}")

        self._finalize_wave(wave, results)
        return results

    def run_wave_2(self, dry_run: bool = False) -> Dict:
        """Wave 2: synthesis + journalist overview articles."""
        wave = 2
        print(f"\n{'='*60}")
        print(f"WELLE 2 — Synthese & Überblicksartikel")
        print(f"{'='*60}\n")

        results = {"wave": 2, "articles_written": [], "errors": []}
        all_entries = self.kb.list_all()

        # Let journalist identify clusters
        clusters = self.journalist.identify_clusters(all_entries)
        print(f"  Cluster identifiziert: {len(clusters)}")

        for cluster in clusters[:4]:
            cluster_name = cluster["name"]
            cluster_titles = cluster["items"]
            cluster_entries = [
                e for e in all_entries
                if any(t.lower() in e["meta"].get("title", "").lower()
                       for t in cluster_titles)
            ][:6]

            if len(cluster_entries) >= 2 and not dry_run:
                try:
                    path = self.journalist.write_overview(
                        cluster_name, cluster_entries, wave=wave
                    )
                    if path:
                        results["articles_written"].append(cluster_name)
                except Exception as e:
                    print(f"  [FEHLER Journalist] {cluster_name}: {e}")
                    results["errors"].append({"cluster": cluster_name, "error": str(e)})

        self._finalize_wave(wave, results)
        return results

    def run_wave_3(self, dry_run: bool = False) -> Dict:
        """Wave 3: curated anthropology of agency life — culture, power, dark sides."""
        wave = 3
        print(f"\n{'='*60}")
        print(f"WELLE 3 — Anthropologie des Agenturlebens")
        print(f"{'='*60}\n")

        results = {"wave": 3, "topics_done": [], "errors": []}
        self.historiker.use_web = True
        total = sum(len(v) for v in WAVE_3_TOPICS.values())
        done = 0

        for category, topics in WAVE_3_TOPICS.items():
            print(f"\n[{category.upper()}]")
            for topic in topics:
                done += 1
                if self.kb.exists(category, topic):
                    print(f"  [skip] {topic}")
                    results["topics_done"].append(topic)
                    continue
                if dry_run:
                    print(f"  [dry-run] {topic}")
                    continue
                try:
                    if category == "visuals":
                        path = self.bildredakteur.research_visuals(topic, wave=wave)
                    else:
                        path = self.historiker.research(topic, wave=wave)
                    if path:
                        results["topics_done"].append(topic)
                except Exception as e:
                    print(f"  [FEHLER] {topic}: {e}")
                    results["errors"].append({"topic": topic, "error": str(e)})
                print(f"  Progress: {done}/{total}")

        self._finalize_wave(wave, results)
        return results

    def run_gap_wave(self, dry_run: bool = False) -> Dict:
        """Gap wave: research topics identified as missing."""
        wave = self._current_wave() + 1
        print(f"\n{'='*60}")
        print(f"WELLE {wave} — Lücken-Forschung")
        print(f"{'='*60}\n")

        existing = [e["meta"].get("title", "") for e in self.kb.list_all()]
        gap_topics = self.historiker.suggest_gaps(existing)

        print(f"  Identifizierte Lücken ({len(gap_topics)}):")
        for t in gap_topics:
            print(f"    - {t}")

        results = {"wave": wave, "topics_done": [], "errors": []}
        self.historiker.use_web = True

        for topic in gap_topics:
            if dry_run:
                print(f"  [dry-run] {topic}")
                continue
            try:
                path = self.historiker.research(topic, wave=wave)
                if path:
                    results["topics_done"].append(topic)
            except Exception as e:
                print(f"  [FEHLER] {topic}: {e}")
                results["errors"].append({"topic": topic, "error": str(e)})

        self._finalize_wave(wave, results)
        return results

    def run_verify_wave(self, dry_run: bool = False, categories: List[str] = None) -> Dict:
        """Verification wave: fact-check all KB entries against web sources and rewrite hallucinated content."""
        wave = self._current_wave() + 1
        print(f"\n{'='*60}")
        print(f"VERIFIKATIONS-WELLE — Faktenprüfung aller Einträge")
        print(f"{'='*60}\n")

        cats = categories or [c for c in CATEGORIES if c != "visuals"]
        all_entries = [e for e in self.kb.list_all() if e["path"].parent.name in cats]
        total = len(all_entries)

        results = {
            "wave": wave,
            "checked": 0,
            "corrected": [],
            "ok": 0,
            "skipped": 0,
            "errors": [],
        }

        print(f"  {total} Einträge in {len(cats)} Kategorien werden geprüft\n")

        for i, entry in enumerate(all_entries, 1):
            title = entry["meta"].get("title", entry["path"].stem)
            print(f"  [{i}/{total}]", end=" ")

            if dry_run:
                print(f"[dry-run] {title[:60]}")
                results["skipped"] += 1
                continue

            try:
                corrected = self.verifier.verify_entry(entry, wave=wave)
                results["checked"] += 1
                if corrected:
                    results["corrected"].append(title)
                else:
                    results["ok"] += 1
            except Exception as e:
                print(f"  [FEHLER] {title[:50]}: {e}")
                results["errors"].append({"title": title, "error": str(e)})

        print(f"\n  Ergebnis: {results['checked']} geprüft, "
              f"{len(results['corrected'])} korrigiert, "
              f"{len(results['errors'])} Fehler")

        if results["corrected"]:
            print("\n  Korrigierte Einträge:")
            for t in results["corrected"]:
                print(f"    ✗ {t}")

        # ── Beiwerk: ungelöste Wikilinks als neue Themen recherchieren ──────
        if not dry_run:
            gaps = self._collect_wikilink_gaps(max_gaps=20, min_mentions=2)
            if gaps:
                print(f"\n  [Beiwerk] {len(gaps)} ungelöste Wikilinks → recherchieren")
                self.historiker.use_web = True
                for raw_name, count in gaps:
                    print(f"    [{count}×] {raw_name}")
                    try:
                        path = self.historiker.research(raw_name, wave=wave)
                        if path:
                            results.setdefault("gaps_researched", []).append(raw_name)
                    except Exception as e:
                        print(f"  [FEHLER Beiwerk] {raw_name}: {e}")
                        results["errors"].append({"title": raw_name, "error": str(e)})

        if not dry_run:
            self._finalize_wave(wave, results)
        return results

    def run_strict_verify_wave(self, dry_run: bool = False,
                               categories: List[str] = None,
                               no_bycatch: bool = False) -> Dict:
        """Strict verification wave: every claim needs a source, unsourced = marked, invented = deleted."""
        wave = self._current_wave() + 1
        print(f"\n{'='*60}")
        print(f"STRENGE VERIFIKATION — Quellenpflicht für alle Einträge")
        print(f"{'='*60}\n")
        print("  Prinzip: Kein Satz ohne Beleg.")
        print("  Ungesichertes → [ungesichert]")
        print("  Erfundenes → gelöscht\n")

        cats = categories or [c for c in CATEGORIES if c != "visuals"]
        all_entries = [e for e in self.kb.list_all() if e["path"].parent.name in cats]
        total = len(all_entries)

        results = {
            "wave": wave,
            "checked": 0,
            "rewritten": [],
            "skipped": 0,
            "errors": [],
        }
        print(f"  {total} Einträge · {len(cats)} Kategorien\n")

        for i, entry in enumerate(all_entries, 1):
            title = entry["meta"].get("title", entry["path"].stem)
            print(f"  [{i}/{total}]", end=" ")
            if dry_run:
                print(f"[dry-run] {title[:65]}")
                results["skipped"] += 1
                continue
            try:
                changed = self.strict_verifier.verify_entry(entry, wave=wave)
                results["checked"] += 1
                if changed:
                    results["rewritten"].append(title)
            except Exception as e:
                print(f"    [FEHLER] {e}")
                results["errors"].append({"title": title, "error": str(e)})

        print(f"\n  Ergebnis: {results['checked']} geprüft, "
              f"{len(results['rewritten'])} überarbeitet, "
              f"{len(results['errors'])} Fehler")

        # Beiwerk: ungelöste Wikilinks recherchieren (nur wenn nicht deaktiviert)
        if not dry_run:
            if not no_bycatch:
                gaps = self._collect_wikilink_gaps(max_gaps=20, min_mentions=2)
                if gaps:
                    print(f"\n  [Beiwerk] {len(gaps)} neue Lücken → recherchieren")
                    self.historiker.use_web = True
                    for raw_name, count in gaps:
                        print(f"    [{count}×] {raw_name}")
                        try:
                            path = self.historiker.research(raw_name, wave=wave)
                            if path:
                                results.setdefault("gaps_researched", []).append(raw_name)
                        except Exception as e:
                            results["errors"].append({"title": raw_name, "error": str(e)})

            self._finalize_wave(wave, results)
        return results

    def run_relevance_wave(self, dry_run: bool = False,
                           categories: List[str] = None,
                           force: bool = False) -> Dict:
        """Narrative enrichment: rewrite articles for story, context and significance."""
        wave = self._current_wave() + 1
        cats = categories or CATEGORIES
        results: Dict = {"enriched": [], "skipped": [], "errors": []}

        entries = []
        for cat in cats:
            entries.extend(self.kb.list_category(cat))

        total = len(entries)
        print(f"\n============================================================")
        print(f"RELEVANZWELLE — Narrative Anreicherung")
        print(f"============================================================")
        print(f"\n  Prinzip: Fakten bleiben, Geschichten kommen rein.")
        print(f"  [ungesichert]-Markierungen bleiben erhalten.")
        print(f"  Dünne Quellenlage wird offen benannt.\n")
        print(f"  {total} Einträge · {len(cats)} Kategorien\n")

        for i, entry in enumerate(entries, 1):
            meta = entry["meta"]
            title = meta.get("title", entry["path"].stem)

            if not force and meta.get("relevance_wave"):
                results["skipped"].append(title)
                continue

            if dry_run:
                print(f"  [{i}/{total}]   [Redakteur] {title[:65]} [dry-run]")
                continue

            try:
                changed = self.redakteur.enrich_entry(entry, wave)
                if changed:
                    results["enriched"].append(title)
                else:
                    results["skipped"].append(title)
            except Exception as e:
                results["errors"].append({"title": title, "error": str(e)})
                print(f"    ✗ {e}")

        if not dry_run:
            self._finalize_wave(wave, results)

        enriched = len(results["enriched"])
        print(f"\n✓ Relevanzwelle abgeschlossen: {enriched} Artikel angereichert, "
              f"{len(results['skipped'])} übersprungen, {len(results['errors'])} Fehler")
        return results

    def run_image_wave(self, dry_run: bool = False,
                       categories: List[str] = None,
                       force: bool = False) -> Dict:
        """Enrich KB articles with real media: images (Commons/OpenVerse) + YouTube videos."""
        import frontmatter as fm
        from agents.media_finder import MediaFinder
        from pathlib import Path as _Path

        wave = self._current_wave() + 1
        cats = categories or CATEGORIES
        cache_dir = _Path(__file__).parent / ".media_cache"
        finder = MediaFinder(cache_dir=cache_dir)

        results: Dict = {"enriched": [], "skipped": [], "errors": []}
        entries = []
        for cat in cats:
            entries.extend(self.kb.list_category(cat))

        total = len(entries)
        print(f"\n[Mediawelle] {total} Einträge · cache: {cache_dir}")
        print(f"  Quellen: Wikimedia Commons · OpenVerse · YouTube\n")

        for i, entry in enumerate(entries, 1):
            meta = entry["meta"]
            title = meta.get("title", entry["path"].stem)
            cat = entry["path"].parent.name
            path = entry["path"]

            if not force and meta.get("images"):
                results["skipped"].append(title)
                print(f"  [{i}/{total}] ↷ {title} (bereits vorhanden)")
                continue

            print(f"  [{i}/{total}] 🔍 {title}", end="", flush=True)

            if dry_run:
                print(" [dry-run]")
                continue

            try:
                media = finder.find_media(title, cat, max_images=2, max_videos=1, meta=meta)
                if media:
                    post = fm.load(str(path))
                    post.metadata["images"] = media
                    path.write_text(fm.dumps(post), encoding="utf-8")
                    results["enriched"].append(title)
                    imgs = sum(1 for m in media if m.get("type") == "image")
                    vids = sum(1 for m in media if m.get("type") == "video")
                    parts = []
                    if imgs: parts.append(f"{imgs} Bild(er)")
                    if vids: parts.append(f"{vids} Video(s)")
                    print(f" → {', '.join(parts)}")
                else:
                    results["skipped"].append(title)
                    print(" → keine Medien gefunden")
            except Exception as e:
                results["errors"].append({"title": title, "error": str(e)})
                print(f" ✗ {e}")

        if not dry_run:
            self._finalize_wave(wave, results)

        enriched = len(results["enriched"])
        print(f"\n[Bildwelle] Abgeschlossen: {enriched} angereichert, "
              f"{len(results['skipped'])} übersprungen, {len(results['errors'])} Fehler")
        return results

    def run_review_wave(self, seed: int = 42, scale: int = 1,
                        only: list = None) -> Dict:
        """Run review agents and save a combined report.
        scale: 1=13 articles, 2=~25, 3=~35
        only: list of reviewer indices (1,2,3) to run; default=all
        """
        from agents.reviewers import ReviewerArchivar, ReviewerCopywriter, ReviewerJournalist
        from tools.review_sampler import ReviewSampler

        wave = self._current_wave() + 1
        label = f"scale={scale}" + (f", nur {only}" if only else "")
        print(f"\n[Review-Welle {wave}] Gutachter analysieren den Korpus ({label}) …\n")

        sample = ReviewSampler(self.kb, seed=seed, scale=scale).prepare()
        sample_titles = [a["title"] for a in sample["articles"]]
        print(f"  Stichprobe ({len(sample_titles)} Artikel):")
        for t in sample_titles:
            print(f"    · {t}")
        print()

        all_reviewers = [
            (1, "Archivar & Lexikograf",          ReviewerArchivar()),
            (2, "Copywriter & Agentur-Historiker", ReviewerCopywriter()),
            (3, "Fachbuchkritiker & Journalist",   ReviewerJournalist()),
        ]
        reviewers = [(i, lbl, r) for i, lbl, r in all_reviewers
                     if only is None or i in only]

        reports = {}
        for _, label, reviewer in reviewers:
            print(f"  ─── {label} ───")
            report = reviewer.review(sample)
            reports[label] = report
            print(f"    ✓ {len(report)} Zeichen\n")

        # Write combined markdown report
        wave_dir = WAVES_DIR / f"wave-{wave:03d}"
        wave_dir.mkdir(parents=True, exist_ok=True)

        from datetime import datetime as _dt
        header = (
            f"# Review-Gutachten — The Longlist\n\n"
            f"*Erstellt: {_dt.now().strftime('%Y-%m-%d')} · "
            f"Stichprobe: {len(sample_titles)} Artikel · Korpus: {len(list(self.kb.list_all()))} Einträge*\n\n"
            f"**Stichprobe:** {', '.join(sample_titles)}\n\n"
            f"**Korpus-Übersicht:**\n```\n{sample['corpus_stats']}\n```\n\n---\n\n"
        )
        body = ""
        for label, report in reports.items():
            body += f"# Gutachten: {label}\n\n{report}\n\n---\n\n"

        full_report = header + body
        report_path = wave_dir / "review_report.md"
        report_path.write_text(full_report, encoding="utf-8")
        print(f"  [Review] Bericht gespeichert: {report_path}")

        # Also save to a fixed path for easy access
        latest = Path(__file__).parent / "waves" / "review_latest.md"
        latest.write_text(full_report, encoding="utf-8")
        print(f"  [Review] Letztes Review: {latest}\n")

        return {"report_path": str(report_path), "reviewers": list(reports.keys())}

    def run_style_wave(self, dry_run: bool = False) -> Dict:
        """Fix 'mehr als nur / more than just' tic across all Überblick sections."""
        from agents.style_fixer import StyleFixer
        fixer = StyleFixer(self.kb)
        return fixer.run_wave(dry_run=dry_run)

    def _collect_wikilink_gaps(self, max_gaps: int = 20, min_mentions: int = 2) -> list:
        """Scan all KB content for [[wikilinks]] that have no matching KB entry. Returns (name, count) pairs."""
        import re
        from collections import Counter
        # Build set of known entry stems
        existing_stems = {e["path"].stem for e in self.kb.list_all()}
        # Also build a slugify-comparable set
        from agents.historiker import _clean_content  # not needed; use inline slugify
        def _slug(t):
            import re as _re
            s = t.lower()
            for a, b in [("ä","ae"),("ö","oe"),("ü","ue"),("ß","ss")]:
                s = s.replace(a, b)
            s = _re.sub(r"[^a-z0-9_]+", "_", s)
            return s.strip("_")[:80]

        existing_slugs = {_slug(s) for s in existing_stems}
        # Also index by title slug and short name
        for e in self.kb.list_all():
            title = e["meta"].get("title", "")
            if title:
                existing_slugs.add(_slug(title))
                short = re.split(r'\s[—–-]\s', title)[0].strip()
                if short:
                    existing_slugs.add(_slug(short))
                # tags as aliases
                for tag in e["meta"].get("tags", []):
                    if tag:
                        existing_slugs.add(_slug(str(tag)))

        # For prefix matching: a link resolves if its slug is a prefix of any existing stem
        def _resolves(raw: str) -> bool:
            s = _slug(raw)
            if s in existing_slugs:
                return True
            # prefix match: "doyle_dane_bernbach" → "doyle_dane_bernbach_ddb__..."
            for stem in existing_stems:
                if stem.startswith(s + "_") or stem.startswith(s + "__"):
                    return True
            return False

        mentions: Counter = Counter()
        wl_re = re.compile(r'\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]')
        for e in self.kb.list_all():
            for m in wl_re.finditer(e["content"]):
                raw = m.group(1).strip()
                if raw and not _resolves(raw) and len(raw) > 4:
                    mentions[raw] += 1

        return [(name, cnt) for name, cnt in mentions.most_common(max_gaps) if cnt >= min_mentions]

    def _finalize_wave(self, wave: int, results: Dict):
        """After every wave: update graph, enrich links, build wiki, write gap report."""
        print(f"\n[POST-WAVE {wave}]")
        existing_titles = [e["meta"].get("title", "") for e in self.kb.list_all()]

        self.archivar.update_graph()
        self.archivar.generate_gap_report(existing_titles, wave)
        self.wiki.build()

        wave_dir = WAVES_DIR / f"wave-{wave:03d}"
        wave_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "wave": wave,
            "timestamp": datetime.now().isoformat(),
            "stats": self.kb.get_stats(),
            **results,
        }
        (wave_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2)
        )
        print(f"  [Wave {wave}] Abgeschlossen. Einträge: {self.kb.get_stats()['total']}")

    def _current_wave(self) -> int:
        waves = sorted(WAVES_DIR.glob("wave-*/manifest.json")) if WAVES_DIR.exists() else []
        if not waves:
            return 0
        last = json.loads(waves[-1].read_text())
        return last.get("wave", 0)

    def status(self):
        stats = self.kb.get_stats()
        print(f"\n{'='*50}")
        print("RECHERCHE STATUS")
        print(f"{'='*50}")
        from config import CATEGORY_LABELS
        for cat in CATEGORIES:
            label = CATEGORY_LABELS.get(cat, cat)
            print(f"  {label:<25} {stats.get(cat, 0):>3} Einträge")
        print(f"  {'─'*30}")
        print(f"  {'Gesamt':<25} {stats['total']:>3} Einträge")

        wave_num = self._current_wave()
        print(f"\n  Letzte Welle: {wave_num}")
        wiki_index = Path(__file__).parent / "wiki" / "index.html"
        if wiki_index.exists():
            print(f"  Wiki: {wiki_index}")
        print()

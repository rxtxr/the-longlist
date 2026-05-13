#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
"""
Agency Tycoon — Research Room
Recherche-Netzwerk zur Geschichte von Werbeagenturen.

Usage:
  python research_room.py --wave 0          # Bootstrap: alle Seed-Themen
  python research_room.py --wave 1          # Vertiefung mit Web-Recherche
  python research_room.py --wave 2          # Synthese & Überblicksartikel
  python research_room.py --wave gap        # Lücken-Forschung
  python research_room.py --topic "Name"   # Einzelnes Thema recherchieren
  python research_room.py --wiki           # Wiki neu bauen
  python research_room.py --status         # Aktuellen Stand zeigen
  python research_room.py --dry-run --wave 0  # Was würde passieren?
"""
import argparse
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    def header(text):
        console.print(Panel(f"[bold yellow]{text}[/]", expand=False))
except ImportError:
    def header(text):
        print(f"\n{'='*60}\n{text}\n{'='*60}")


def check_api_key():
    try:
        from config import TOGETHER_API_KEY
        if not TOGETHER_API_KEY:
            print("FEHLER: TOGETHER_API_KEY nicht gesetzt.")
            print("Prüfe: /home/rxtxr/projects/agency-tycoon/.env")
            sys.exit(1)
    except Exception as e:
        print(f"FEHLER beim Laden der Konfiguration: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Agency Tycoon Research Room",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--wave", type=str, metavar="N|gap",
                        help="Welle ausführen (0=Bootstrap, 1=Web, 2=Synthese, gap=Lücken)")
    parser.add_argument("--topic", type=str,
                        help="Einzelnes Thema recherchieren")
    parser.add_argument("--category", type=str, default=None,
                        help="Kategorie für --topic (agencies, people, eras, ...)")
    parser.add_argument("--wiki", action="store_true",
                        help="Wiki neu generieren")
    parser.add_argument("--status", action="store_true",
                        help="Status und Statistiken anzeigen")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur planen, nichts ausführen")
    parser.add_argument("--no-web", action="store_true",
                        help="Keine Web-Suche verwenden")
    parser.add_argument("--visual", type=str,
                        help="Bildmaterial zu einem Thema recherchieren")
    parser.add_argument("--graph", action="store_true",
                        help="Wissensgraph (graph.json + graph.html) neu bauen")
    parser.add_argument("--enrich", action="store_true",
                        help="Ontologie-Anreicherung aller Einträge (heuristisch)")
    parser.add_argument("--verify", action="store_true",
                        help="Faktenprüfung: alle Einträge gegen Web-Quellen verifizieren")
    parser.add_argument("--verify-cat", type=str, default=None,
                        help="Nur eine Kategorie verifizieren (z.B. agencies)")
    parser.add_argument("--strict-verify", action="store_true",
                        help="Strenge Quellenpflicht: ungesichertes markieren, erfundenes löschen")
    parser.add_argument("--no-bycatch", action="store_true",
                        help="Kein Beiwerk: keine Lücken-Recherche nach Verifikation")
    parser.add_argument("--image-wave", action="store_true",
                        help="Bildwelle: echte Bilder von Wikimedia Commons einfügen")
    parser.add_argument("--image-force", action="store_true",
                        help="Bildwelle auch für Einträge mit vorhandenen Bildern wiederholen")
    parser.add_argument("--relevance-wave", action="store_true",
                        help="Relevanzwelle: Artikel narrativ anreichern (Geschichten, Kontext, Bedeutung)")
    parser.add_argument("--relevance-force", action="store_true",
                        help="Relevanzwelle auch für bereits bearbeitete Einträge wiederholen")
    parser.add_argument("--style-wave", action="store_true",
                        help="Stilwelle: 'mehr als nur / more than just'-Muster in Überblick-Abschnitten bereinigen")
    parser.add_argument("--review", action="store_true",
                        help="Review-Welle: drei Gutachter analysieren Muster, Ton und Qualität des Korpus")
    parser.add_argument("--review-seed", type=int, default=42,
                        help="Zufalls-Seed für Artikel-Stichprobe (default: 42)")
    parser.add_argument("--review-scale", type=int, default=1,
                        help="Stichprobengröße: 1=~13, 2=~25, 3=~35 Artikel")
    parser.add_argument("--review-only", type=str, default=None,
                        help="Nur bestimmte Gutachter: z.B. '2,3' für Copywriter+Journalist")
    args = parser.parse_args()

    if not any([args.wave, args.topic, args.wiki, args.status, args.visual, args.graph, args.enrich, args.verify, args.strict_verify, args.image_wave, args.relevance_wave, args.review, args.style_wave]):
        parser.print_help()
        print("\nBeispiel: python research_room.py --status")
        return

    if not args.status:
        check_api_key()


    from tools.knowledge_base import KnowledgeBase
    from wave_runner import WaveRunner

    kb = KnowledgeBase()
    runner = WaveRunner(kb)

    if args.status:
        runner.status()
        return

    if args.enrich:
        header("Ontologie-Anreicherung")
        import scripts.enrich_ontology as enrich
        enrich.main()
        return

    if args.verify:
        cats = [args.verify_cat] if args.verify_cat else None
        label = args.verify_cat or "alle Kategorien"
        header(f"Faktenprüfung — {label}")
        results = runner.run_verify_wave(dry_run=args.dry_run, categories=cats)
        corrected = len(results.get("corrected", []))
        print(f"\n✓ Verifikation abgeschlossen: {corrected} Artikel korrigiert")
        return

    if args.strict_verify:
        cats = [args.verify_cat] if args.verify_cat else None
        label = args.verify_cat or "alle Kategorien"
        header(f"Strenge Verifikation — {label}")
        results = runner.run_strict_verify_wave(dry_run=args.dry_run, categories=cats, no_bycatch=getattr(args, "no_bycatch", False))
        rewritten = len(results.get("rewritten", []))
        print(f"\n✓ Strenge Verifikation abgeschlossen: {rewritten} Artikel überarbeitet")
        return

    if args.relevance_wave:
        cats = [args.verify_cat] if args.verify_cat else None
        label = args.verify_cat or "alle Kategorien"
        header(f"Relevanzwelle — {label}")
        results = runner.run_relevance_wave(
            dry_run=args.dry_run,
            categories=cats,
            force=getattr(args, "relevance_force", False),
        )
        enriched = len(results.get("enriched", []))
        print(f"\n✓ Relevanzwelle abgeschlossen: {enriched} Artikel angereichert")
        return

    if args.image_wave:
        cats = [args.verify_cat] if args.verify_cat else None
        label = args.verify_cat or "alle Kategorien"
        header(f"Bildwelle — {label}")
        results = runner.run_image_wave(
            dry_run=args.dry_run,
            categories=cats,
            force=getattr(args, "image_force", False),
        )
        enriched = len(results.get("enriched", []))
        print(f"\n✓ Bildwelle abgeschlossen: {enriched} Artikel angereichert")
        return

    if args.style_wave:
        header("Stilwelle: 'mehr als nur'-Bereinigung")
        results = runner.run_style_wave(dry_run=args.dry_run)
        print(f"\n✓ Stilwelle: {results['fixed']} Artikel überarbeitet")
        return

    if args.review:
        header("Review-Welle: Gutachter")
        only = None
        if getattr(args, "review_only", None):
            only = [int(x.strip()) for x in args.review_only.split(",")]
        results = runner.run_review_wave(
            seed=getattr(args, "review_seed", 42),
            scale=getattr(args, "review_scale", 1),
            only=only,
        )
        print(f"\n✓ Review abgeschlossen → {results['report_path']}")
        return

    if args.graph:
        header("Wissensgraph bauen")
        from tools.graph_builder import GraphBuilder
        from tools.wiki_builder import WikiBuilder
        GraphBuilder(kb).build()
        WikiBuilder(kb)._build_graph_page()
        graph_path = Path(__file__).parent / "wiki" / "graph.html"
        print(f"\n✓ Graph: {graph_path}")
        return

    if args.wiki:
        header("Wiki generieren")
        from tools.wiki_builder import WikiBuilder
        WikiBuilder(kb).build()
        wiki_path = Path(__file__).parent / "wiki" / "index.html"
        print(f"\n✓ Wiki: {wiki_path}")
        return

    if args.topic:
        header(f"Recherche: {args.topic}")
        runner.historiker.use_web = not args.no_web
        path = runner.historiker.research(args.topic, wave=99)
        if path:
            print(f"\n✓ Gespeichert: {path}")
            runner.archivar.update_graph()
            from tools.wiki_builder import WikiBuilder
            WikiBuilder(kb).build()
        return

    if args.visual:
        header(f"Bildrecherche: {args.visual}")
        path = runner.bildredakteur.research_visuals(args.visual, wave=99)
        if path:
            print(f"\n✓ Gespeichert: {path}")
        return

    if args.wave:
        wave = args.wave.lower()
        dry = args.dry_run

        if wave == "0":
            header("Welle 0 — Bootstrap")
            runner.run_wave_0(dry_run=dry)
        elif wave == "1":
            header("Welle 1 — Vertiefung")
            runner.run_wave_1(dry_run=dry)
        elif wave == "2":
            header("Welle 2 — Synthese")
            runner.run_wave_2(dry_run=dry)
        elif wave == "3":
            header("Welle 3 — Anthropologie")
            runner.run_wave_3(dry_run=dry)
        elif wave == "gap":
            header("Lücken-Welle")
            runner.run_gap_wave(dry_run=dry)
        else:
            print(f"Unbekannte Welle: {wave}. Gültig: 0, 1, 2, 3, gap")
            sys.exit(1)

        wiki_path = Path(__file__).parent / "wiki" / "index.html"
        print(f"\n✓ Wiki aktualisiert: {wiki_path}")


if __name__ == "__main__":
    main()

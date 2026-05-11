#!/usr/bin/env python3
"""One-time migration: move misclassified entries from agencies/ to correct categories."""
import warnings; warnings.filterwarnings("ignore")
import shutil
from pathlib import Path
import frontmatter as fm

KB = Path("knowledge")
OBS = Path("/home/rxtxr/Dokumente/rxtxr/Agenturgeschichte")

# ── Umzugsplan: Dateiname (ohne .md) → Ziel-Kategorie ─────────────────────
MOVES = {
    # ── LIFE: Agenturalltag, Rollen, Kultur, Macht ─────────────────────────
    "abwerben_von_kreativen_und_kunden_headhunter_und_wechselkultur_in_der_werbebranc": "life",
    "account_manager_vs_kreative_die_ewige_feindschaft_zwischen_suits_und_jeans":       "life",
    "agentur_hierarchien_und_organigramme_1950_1980":                                   "life",
    "agentur_hierarchien_und_organigramme_von_der_boutique_zum_netzwerk":               "life",
    "agenturkultur_partys_rituale_und_firmenmythen":                                    "life",
    "agentur_rankings_in_fachzeitschriften_w_v_horizont_campaign_advertising_age":      "life",
    "agentur_spin_offs_und_gruendungsmythen_wenn_kreative_die_mutterfirma_verlassen":   "life",
    "arbeitsalltag_in_einer_werbeagentur_der_1980er_jahre":                             "life",
    "buerodesign_als_markensignal_wie_werbeagenturen_ihre_raeume_fuer_kunden_inszenie": "life",
    "cannes_als_klassentreffen_was_jenseits_der_awards_in_cannes_wirklich_passiert":    "life",
    "das_briefing_wie_auftraege_in_agenturen_ankommen_und_bearbeitet_werden":           "life",
    "das_kreativ_briefing_ritual_missverstaendnis_und_neuverhandlung":                  "life",
    "der_creative_director_entstehung_der_rolle":                                       "life",
    "die_fachpresse_als_machtinstrument_wer_in_w_v_und_horizont_erscheint":            "life",
    "die_jahresetat_praesentation_agenturalltag":                                       "life",
    "die_rolle_des_account_managers_in_der_klassischen_agentur":                        "life",
    "die_rolle_des_media_planers_in_der_werbeagentur":                                  "life",
    "grosskunden_macht_wenn_der_client_mehr_zu_sagen_hat_als_der_creative_director":    "life",
    "honorarmodelle_15_provision_vs_fee_system":                                        "life",
    "kunden_mitnehmen_beim_agenturwechsel_das_etat_mitnahme_phaenomen":                "life",
    "kundenpflege_und_kundenunterhaltung_dinner_reisen_gefaelligkeiten":                "life",
    "pitch_kultur_und_der_all_nighter_ueberstunden_romantik_und_erschoepfung":         "life",
    "praesentationsraeume_und_pitch_material_aesthetik":                                "life",
    "tagesablauf_in_einer_werbeagentur_der_1960er_jahre":                               "life",
    "tagesablauf_und_arbeitsalltag_in_einer_werbeagentur_der_1960er_jahre":             "life",

    # ── ERAS: regionale Szenen, Branchenentwicklungen, Epochen ─────────────
    "die_aera_der_werbenetze_und_holdinggesellschaften_1980_2000":                      "eras",
    "die_hamburger_werbeszene_von_ggk_ueber_springer_jacoby_zu_jung_von_matt":          "eras",
    "die_muenchner_werbeszene_bayern_als_zweites_zentrum_neben_hamburg_und_duesseldor": "eras",
    "die_geschichte_der_oesterreichischen_werbeszene_und_ihre_praegung_durch_hans_dom": "eras",
    "werbebranche_in_der_schweiz_wirz_ruf_lanz_advico_und_helvetica":                   "eras",
    "die_entstehung_und_entwicklung_der_direct_marketing_agenturen_1960er_1990er":      "eras",
    "die_entwicklung_der_media_agenturen_und_ihre_trennung_von_den_full_service_agent": "eras",
    "die_entwicklung_der_internen_kommunikation_als_werbedisziplin_corporate_publishi": "eras",

    # ── PHILOSOPHY: strategische und methodische Konzepte ──────────────────
    "account_planning_stephen_king_und_der_strategische_planer":                        "philosophy",
    "brand_image_david_ogilvys_markenphilosophie":                                      "philosophy",
    "die_rolle_der_marktforschung_in_der_werbeagentur_vor_und_nach_account_planning":   "philosophy",

    # ── TECHNOLOGY: Technik, Studios, Ausstattung ──────────────────────────
    "fotoatelier_in_der_werbeagentur_studio_beleuchtung_kameras":                       "technology",
    "fotoatelier_und_fotostudio_in_der_agentur":                                        "technology",

    # ── SCANDALS: Kontroversen und Skandale ────────────────────────────────
    "benetton_und_oliviero_toscani_schockwerbung":                                      "scandals",

    # ── WORK: Prozesse, Pitches, Verbände ──────────────────────────────────
    "der_pitch_geschichte_und_ablauf_eines_werbepitches":                               "work",
    "die_rolle_von_werbeclubs_und_berufsverbaenden_z_b_adc_d_ad_art_directors_club":    "work",

    # ── PEOPLE: Einzelpersonen ─────────────────────────────────────────────
    "helmut_pantke_ggk_und_die_deutsche_agenturlandschaft":                             "people",

    # ── VISUALS: visuelle Dokumente ────────────────────────────────────────
    "visuelles_aus_dem_agenturalltag_bueros_und_studios_der_1960er":                    "visuals",
}

TYPE_MAP = {
    "agencies": "agency", "people": "person", "eras": "era",
    "work": "work", "life": "life", "technology": "technology",
    "philosophy": "philosophy", "scandals": "scandal", "visuals": "visual",
}

moved = 0
skipped = 0
errors = []

for slug, target_cat in MOVES.items():
    src = KB / "agencies" / f"{slug}.md"
    if not src.exists():
        skipped += 1
        continue

    dst_dir = KB / target_cat
    dst_dir.mkdir(exist_ok=True)
    dst = dst_dir / f"{slug}.md"

    # Update frontmatter type field
    try:
        post = fm.load(str(src))
        post.metadata["type"] = TYPE_MAP.get(target_cat, target_cat)
        dst.write_text(fm.dumps(post), encoding="utf-8")
        src.unlink()
    except Exception as e:
        errors.append(f"{slug}: {e}")
        continue

    # Mirror move in Obsidian vault
    obs_src = OBS / "agencies" / f"{slug}.md"
    obs_dst_dir = OBS / target_cat
    obs_dst_dir.mkdir(exist_ok=True)
    if obs_src.exists():
        shutil.move(str(obs_src), str(obs_dst_dir / f"{slug}.md"))

    moved += 1
    print(f"  agencies/ → {target_cat}/  {slug[:60]}")

print(f"\nVerschoben: {moved}  |  Nicht gefunden: {skipped}  |  Fehler: {len(errors)}")
if errors:
    for e in errors:
        print(f"  FEHLER: {e}")

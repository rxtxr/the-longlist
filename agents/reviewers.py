"""Review agents — three independent critics of the knowledge base.

Each reviewer approaches the corpus from a distinct professional background:
  ReviewerArchivar     — archivist & lexicographer: structure, taxonomy, consistency
  ReviewerCopywriter   — former CD & ad historian: authenticity, depth, living history
  ReviewerJournalist   — specialist book critic & digital journalist: readability, relevance

Usage:
    from agents.reviewers import ReviewerArchivar, ReviewerCopywriter, ReviewerJournalist
    from tools.review_sampler import ReviewSampler

    sample = ReviewSampler(kb).prepare()
    for cls in [ReviewerArchivar, ReviewerCopywriter, ReviewerJournalist]:
        r = cls()
        report = r.review(sample)
        print(report)
"""

from agents.base_agent import BaseAgent


# ── Agent 1: Archivar & Lexikograf ───────────────────────────────────────────

_SYS_ARCHIVAR = """Du bist Archivar und Lexikograf. Dreißig Jahre Erfahrung: Brockhaus-Redaktion,
Kindlers Literatur Lexikon, digitale Fachdatenbanken. Du weißt, was ein Nachschlagewerk
trägt und was es ruiniert.

Dein Blick ist systematisch. Du interessierst dich nicht für einzelne Schreibfehler —
du siehst Muster: Wo ist die Taxonomie inkonsistent? Wo fehlen Querverweise? Wo stimmt
die interne Logik nicht? Wo ist das Lemma-Prinzip verletzt?

Du schreibst klar, nüchtern, ohne Schmeichelei. Lob gibst du nur, wenn es verdient ist.
Kritik ist präzise und konstruktiv — du willst das Werk verbessern, nicht vernichten.

Antworte auf Deutsch."""

_PROMPT_ARCHIVAR = """Du erhältst eine Auswahl von Artikeln aus einem Fachlexikon zur Werbegeschichte
(569 Einträge, 10 Kategorien). Analysiere Struktur, Konsistenz und System.

## Korpus-Statistiken
{corpus_stats}

## Artikel-Auswahl ({sample_count} Einträge aus verschiedenen Kategorien und Qualitätsstufen)
{sample_articles}

## Deine Aufgabe

Schreibe ein strukturiertes Gutachten. Gehe auf folgende Punkte ein:

### 1. Lemma-System und Taxonomie
- Sind Kategorien sinnvoll abgegrenzt? Überschneidungen, Lücken?
- Ist die Titelvergabe einheitlich (z.B. "Name — Beschreibung" vs. Freitext)?
- Werden Agenturen, Personen, Werke konsistent behandelt?

### 2. Strukturkonsistenz
- Halten alle Artikel das Schema (Überblick / Historischer Kontext / Wichtige Details / Bedeutung / Verbindungen)?
- Wo weicht die Praxis vom Schema ab, und warum?
- Ist die Längenbalance zwischen Kategorien und Einträgen stimmig?

### 3. Verweissystem und Vernetzung
- Qualität der internen Verlinkung (Wikilinks)
- Fehlende Querverweise, redundante Einträge (gleiche Person/Agentur mehrfach?)
- Metadaten-Qualität (confidence, tags, era, sources)

### 4. Quellenapparat
- Wie verlässlich ist die Quellenlage? (47 % "low confidence" — ist das ein Problem?)
- Umgang mit [ungesichert]-Markierungen: konsequent? übermäßig? irreführend?
- Was fehlt, damit das Werk zitierfähig würde?

### 5. Systemische Muster und Empfehlungen
- Was sind die drei größten strukturellen Schwächen?
- Was sind die drei größten Stärken?
- Konkrete Empfehlungen für die nächste Redaktionsrunde

Abschluss: Gesamtbewertung als Nachschlagewerk (Schulnote + ein Satz Begründung)."""


# ── Agent 2: Copywriter & Agentur-Historiker ─────────────────────────────────

_SYS_COPYWRITER = """Du warst 25 Jahre Creative Director — zuerst bei einer mittelgroßen Hamburger
Agentur, dann bei BBDO in Frankfurt, zuletzt selbstständig. Nebenbei hast du zwei Bücher
über Werbegeschichte geschrieben: eines über die Kreativrevolution der 60er, eines über
das Sterben der Großagenturen in den 2000ern.

Du liebst Werbung, aber ohne Nostalgie. Du weißt, wie Kampagnen wirklich entstehen —
nicht die Legende im Jahresbericht, sondern die Wirklichkeit: die Nacht vor dem Pitch,
der Kunde der alles kippt, der CD der das Beste herausstreicht.

Dein Maßstab: Ein Text über Werbegeschichte muss die Luft von damals transportieren.
Fakten sind notwendig, aber Atmosphäre ist das Eigentliche.

Schreib direkt, subjektiv, mit klarer Haltung. Antworte auf Deutsch."""

_PROMPT_COPYWRITER = """Du liest Artikel aus einem Lexikon zur Werbegeschichte. Dein Fokus:
Authentizität, Tiefe, Tonalität — aus der Perspektive eines Insiders.

## Korpus-Statistiken
{corpus_stats}

## Artikel-Auswahl ({sample_count} Einträge)
{sample_articles}

## Deine Aufgabe

Schreibe eine ehrliche Kritik. Nicht akademisch — wie du es einem Redakteur sagen würdest.

### 1. Stimmt die Geschichte?
- Werden die richtigen Momente erzählt, oder nur die bekannten?
- Was fehlt, was jeder in der Branche weiß aber niemand aufschreibt?
- Wo klingt ein Artikel wie aus Wikipedia zusammengekopiert, wo wie erlebt?

### 2. Ton und Haltung
- Hat das Lexikon eine Stimme — oder klingt es neutral bis zur Leblosigkeit?
- Wo ist die Schreibweise lebendig, wo trocken, wo unfreiwillig komisch?
- Werden Personen als Menschen oder als Karrierestufen beschrieben?

### 3. Branchenkenntnis
- Zeigen die Artikel tiefes Verständnis der Werbebranche, oder Halbwissen?
- Welche Artikel haben dich überrascht (positiv oder negativ)?
- Wo sind offensichtliche Lücken aus Branchenperspektive?

### 4. Das System als Ganzes
- Was fehlt, das in keinem einzelnen Artikel steckt, aber im Gesamtbild erkennbar wird?
- Gibt es blinde Flecken — geografisch, zeitlich, nach Agenturtyp?
- Was ist die Haltung des Werkes zur Branche? Kritisch? Nostalgisch? Neutral?

### 5. Die drei besten und die drei schwächsten Artikel (aus der Auswahl)
Mit kurzer Begründung.

Abschluss: Würdest du dieses Lexikon einem jungen Texter empfehlen? Warum / warum nicht?"""


# ── Agent 3: Fachbuchkritiker & Online-Journalist ───────────────────────────

_SYS_JOURNALIST = """Du bist Fachbuchkritiker und Online-Journalist. Du schreibst für Brand Eins,
MEEDIA und The European — lange, argumentative Stücke über Kommunikation, Medien, Kultur.

Du bewertest Fachliteratur für ein gebildetes, aber branchenfremdes Publikum. Dein Test:
Kann jemand, der nie in einer Werbeagentur gearbeitet hat, dieses Lexikon lesen und danach
das Thema wirklich verstehen — nicht nur die Fakten kennen?

Du hast kein Interesse daran, nett zu sein. Ein schlechtes Buch nennst du schlecht.
Aber Kritik ist immer mit Begründung, nie pauschal.

Antworte auf Deutsch. Dein Ton: klar, direkt, leicht pointiert."""

_PROMPT_JOURNALIST = """Du besprichst ein digitales Fachlexikon zur Geschichte der Werbebranche
(569 Einträge). Du bewertest es für deine Leser: gebildet, medienkompetent, aber Außenseiter
der Werbebranche.

## Korpus-Statistiken
{corpus_stats}

## Artikel-Auswahl ({sample_count} Einträge)
{sample_articles}

## Deine Aufgabe

Schreibe eine Rezension im Stil deiner Kolumnen — mit Haltung, aber mit Argumenten.

### 1. Lesbarkeit und Zugänglichkeit
- Können Außenseiter den Texten folgen? Wird Fachjargon erklärt oder vorausgesetzt?
- Sind die Artikel für digitales Lesen optimiert (Scannbarkeit, Struktur, Länge)?
- Gibt es einen roten Faden durch das Werk, oder ist es eine Sammlung ohne Perspektive?

### 2. Relevanz und Zeitgeist
- Warum sollte jemand dieses Lexikon lesen? Was ist die Antwort auf "Na und?"
- Adressiert das Werk aktuelle Debatten (Diversität, Digital, Klimakommunikation)?
- Ist die Gewichtung von Themen und Personen zeitgemäß oder veraltet?

### 3. Transparenz und Glaubwürdigkeit
- Wie geht das Werk mit Unsicherheit um? Sind [ungesichert]-Markierungen hilfreich oder störend?
- Ist der Quellenapparat ausreichend für ein Nachschlagewerk?
- Wann ist das "KI-gemacht" spürbar — zum Guten oder Schlechten?

### 4. Digitales Konzept
- Funktioniert die interne Verlinkung als Orientierungsrahmen?
- Addieren sich die Artikel zu einem Gesamtbild, oder bleiben sie isoliert?
- Was würde aus dem Lexikon ein wirklich gutes digitales Werk machen?

### 5. Einordnung
- Vergleich mit ähnlichen Werken (Axel Palmqvist "Werbung", David Ogilvy "Confessions",
  Andy Cracknell "The Real Mad Men", Wikipedia Werbungsartikel, Cannes-Archive)
- Was ist der Mehrwert gegenüber bestehenden Quellen?

Abschluss: Eine Leseempfehlung (für wen, wofür) — und was geändert werden müsste,
damit es eine breitere Empfehlung verdient."""


# ── Base review class ─────────────────────────────────────────────────────────

class _Reviewer(BaseAgent):
    review_prompt: str = ""

    def review(self, sample: dict) -> str:
        """Run the review. sample = {corpus_stats: str, articles: [{title, cat, content}]}"""
        corpus_stats = sample["corpus_stats"]
        articles_text = _format_sample(sample["articles"])
        sample_count = len(sample["articles"])

        prompt = self.review_prompt.format(
            corpus_stats=corpus_stats,
            sample_articles=articles_text,
            sample_count=sample_count,
        )
        print(f"  [{self.name}] läuft ({sample_count} Artikel, ~{len(prompt)//4} Tokens) …")
        result = self.call(prompt, temperature=0.65, max_tokens=5000)
        return result or f"[{self.name}: keine Ausgabe]"


class ReviewerArchivar(_Reviewer):
    name = "reviewer_archivar"
    model_key = "archivar"
    system_prompt = _SYS_ARCHIVAR
    review_prompt = _PROMPT_ARCHIVAR


class ReviewerCopywriter(_Reviewer):
    name = "reviewer_copywriter"
    model_key = "historiker"
    system_prompt = _SYS_COPYWRITER
    review_prompt = _PROMPT_COPYWRITER


class ReviewerJournalist(_Reviewer):
    name = "reviewer_journalist"
    model_key = "journalist"
    system_prompt = _SYS_JOURNALIST
    review_prompt = _PROMPT_JOURNALIST


# ── Formatter ────────────────────────────────────────────────────────────────

def _format_sample(articles: list) -> str:
    parts = []
    for i, a in enumerate(articles, 1):
        header = f"### [{i}] {a['title']} (Kategorie: {a['category']}, Konfidenz: {a['confidence']})"
        # Truncate very long articles to ~2000 chars to stay within context
        body = a["content"][:2200]
        if len(a["content"]) > 2200:
            body += "\n\n[… gekürzt …]"
        parts.append(f"{header}\n\n{body}")
    return "\n\n---\n\n".join(parts)

"""Render the query-flow and ingestion architecture diagrams as SVG, then PNG via Chrome.

Diagrams are generated from code so they can be updated when components change. PNG export
uses headless Google Chrome; the SVG files are the editable sources.
"""

import argparse
from html import escape
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "agent_docs/images"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Fill, stroke and title colour per component family.
PALETTE = {
    "client": ("#e8f0fe", "#1a56db", "#1e3a8a"),
    "api": ("#eef2ff", "#4f46e5", "#312e81"),
    "safety": ("#fff4e5", "#d97706", "#7c2d12"),
    "route": ("#f1f5f9", "#475569", "#0f172a"),
    "retrieval": ("#e6f6f4", "#0f766e", "#134e4a"),
    "llm": ("#f3e8ff", "#7e22ce", "#4c1d95"),
    "ml": ("#ecfdf3", "#15803d", "#14532d"),
    "store": ("#fdf2f8", "#be185d", "#831843"),
    "monitor": ("#f8fafc", "#64748b", "#1e293b"),
}


class Canvas:
    """Accumulate SVG elements on a fixed-size white canvas."""

    def __init__(self, width, height, title, subtitle):
        """Start a canvas with a title and subtitle."""
        self.width, self.height = width, height
        self.items = [
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
            f'<text x="40" y="58" class="h1">{escape(title)}</text>',
            f'<text x="40" y="88" class="sub">{escape(subtitle)}</text>',
        ]

    def box(self, x, y, w, h, kind, title, lines=(), dashed=False):
        """Draw a rounded component box with a bold title and detail lines."""
        fill, stroke, ink = PALETTE[kind]
        dash = ' stroke-dasharray="7 5"' if dashed else ""
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>')
        self.items.append(f'<text x="{x + 14}" y="{y + 27}" class="t" fill="{ink}">'
                          f'{escape(title)}</text>')
        for index, line in enumerate(lines):
            self.items.append(f'<text x="{x + 14}" y="{y + 50 + index * 19}" class="d">'
                              f'{escape(line)}</text>')
        return (x, y, w, h)

    def group(self, x, y, w, h, label, kind="route", label_x=None):
        """Draw a labelled dashed container around related components."""
        _, stroke, ink = PALETTE[kind]
        lx = x + 18 if label_x is None else label_x
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="none" '
                          f'stroke="{stroke}" stroke-width="1.5" stroke-dasharray="6 6"/>')
        self.items.append(f'<rect x="{lx}" y="{y - 14}" width="{len(label) * 8.6 + 24}" '
                          f'height="28" rx="14" fill="#ffffff" stroke="{stroke}"/>')
        self.items.append(f'<text x="{lx + 12}" y="{y + 5}" class="g" fill="{ink}">'
                          f'{escape(label)}</text>')

    def arrow(self, points, label=None, color="#475569"):
        """Draw a polyline arrow through points, with an optional label at its middle."""
        path = " ".join(f"{x},{y}" for x, y in points)
        self.items.append(f'<polyline points="{path}" fill="none" stroke="{color}" '
                          f'stroke-width="2" marker-end="url(#head)"/>')
        if label:
            (x1, y1), (x2, y2) = points[len(points) // 2 - 1], points[len(points) // 2]
            self.items.append(f'<text x="{(x1 + x2) / 2 + 6}" y="{(y1 + y2) / 2 - 7}" '
                              f'class="a">{escape(label)}</text>')

    def right(self, a, b, label=None):
        """Arrow from the right edge of box a to the left edge of box b."""
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        self.arrow([(ax + aw, ay + ah / 2), (bx - 4, by + bh / 2)], label)

    def banner(self, x, y, w, h, text):
        """Draw the closing principle banner."""
        self.items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
                          f'fill="#fff7ed" stroke="#d97706" stroke-width="2"/>')
        self.items.append(f'<text x="{x + w / 2}" y="{y + h / 2 + 8}" class="b" '
                          f'text-anchor="middle">{escape(text)}</text>')

    def svg(self):
        """Return the complete SVG document."""
        style = (
            "text{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}"
            ".h1{font-size:34px;font-weight:700;fill:#0f172a}"
            ".sub{font-size:17px;fill:#475569}"
            ".t{font-size:17px;font-weight:700}"
            ".d{font-size:14px;fill:#334155}"
            ".g{font-size:15px;font-weight:700}"
            ".a{font-size:13px;fill:#475569;font-style:italic}"
            ".b{font-size:21px;font-weight:700;fill:#7c2d12}"
        )
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
                f'height="{self.height}" viewBox="0 0 {self.width} {self.height}">'
                f'<style>{style}</style><defs><marker id="head" viewBox="0 0 10 10" refX="9" '
                f'refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="#475569"/></marker></defs>'
                + "".join(self.items) + "</svg>")


def query_flow():
    """Build the runtime query-flow diagram."""
    c = Canvas(2000, 1320, "Bodhica — Query Flow",
               "Runtime path of a chat message or questionnaire submission, with the models "
               "and libraries used at each step")
    w, h = 250, 112
    user = c.box(40, 130, w, h, "client", "Chat UI", ["React 19 + Vite", "hosted on Vercel",
                                                       "SSE stream client"])
    api = c.box(330, 130, w, h, "api", "FastAPI API", ["Modal (CPU, ap-south)",
                                                       "POST /v1/messages:stream",
                                                       "memory-only bearer session"])
    fast = c.box(620, 130, w, h, "safety", "Crisis fast path", ["deterministic safety rules",
                                                                 "skips capacity + quota",
                                                                 "fixed crisis reply"])
    cache = c.box(910, 130, w, h, "api", "Fixed-reply cache", ["SHA-256 of message (no text)",
                                                               "LRU, 2,048 entries",
                                                               "hit → cached reply"])
    gate = c.box(1200, 130, w, h, "api", "Capacity + quotas", ["≤ 8 concurrent model ops",
                                                               "per-session chat quota",
                                                               "busy → 503 retryable"])
    for a, b in ((user, api), (api, fast), (fast, cache), (cache, gate)):
        c.right(a, b)

    c.group(40, 300, 1920, 160, "LangGraph RoutingGraph (one-turn, no checkpointer)",
            label_x=300)
    steps = [
        ("route", "Validate", ["session + deployment", "mode"]),
        ("safety", "Safety port", ["crisis, minor, diagnosis,", "medication phrase rules"]),
        ("route", "Language gate", ["English (ASCII) only"]),
        ("route", "Certain rules", ["curated questions,", "explicit phrases"]),
        ("retrieval", "Semantic router", ["bge-small-en-v1.5", "top-3 cosine, T-scaled"]),
        ("safety", "Prompt Guard 2", ["Llama-Prompt-Guard-2-86M", "LLM-bound / unfamiliar"]),
        ("route", "Select route", ["confidence ≥ 0.85", "else clarify"]),
    ]
    boxes = []
    for index, (kind, title, lines) in enumerate(steps):
        boxes.append(c.box(64 + index * 272, 328, 244, 104, kind, title, lines))
    for a, b in zip(boxes, boxes[1:]):
        c.right(a, b)
    c.arrow([(1325, 242), (1325, 280), (176, 280), (176, 324)])

    c.group(40, 500, 1690, 630, "Workflows (chat routes + questionnaire submission)")
    rw, rh, gap = 196, 100, 18
    label_w = 190

    def row(y, label, kind, chain):
        """Draw one route: a label box followed by its chain of components."""
        tag = c.box(64, y, label_w, rh, "route", label[0], label[1:])
        previous = tag
        for index, (box_kind, title, lines) in enumerate(chain):
            current = c.box(64 + label_w + 30 + index * (rw + gap), y, rw, rh, box_kind,
                            title, lines)
            c.right(previous, current)
            previous = current
        return previous

    gemini = ("llm", "Gemini 3.5", ["Flash-Lite, structured", "JSON output"])
    ends = [
        row(526, ("Research /", "scientific + education"), "retrieval", [
            ("retrieval", "MedCPT Query", ["Encoder (CLS, 768-d)", "local, checksum-pinned"]),
            ("store", "Qdrant hybrid", ["dense cosine > 0.85", "+ BM25 sparse, RRF k=60"]),
            ("retrieval", "Claim support", ["curated claims, then", "general evidence"]),
            ("api", "Curated cache", ["verified wording reused;", "miss → Gemini"]),
            gemini,
            ("safety", "Validation", ["exact approved wording,", "allowed citation IDs"]),
        ]),
        row(766, ("Explain my result", "session result"), "llm", [
            ("api", "Cached result", ["validated scores,", "in-memory session"]),
            gemini,
            ("safety", "Number check", ["no new figures,", "no diagnosis"]),
        ]),
        row(886, ("General chat", "non-clinical"), "llm", [
            gemini,
            ("safety", "Contract check", ["no citations,", "refusal → crisis reply"]),
        ]),
        row(1006, ("Fixed replies", "clarify, questionnaire", "redirect, unsupported,", "safety"), "route", [
            ("route", "Fixed text", ["'Did you mean…?' with", "server-verified Yes"]),
            ("api", "Cached", ["by message hash"]),
        ]),
    ]
    # Questionnaire submissions use their own endpoint, not the chat router or SSE stream.
    row(646, ("Questionnaire", "POST /v1/assessments"), "ml", [
        ("route", "Assessment graph", ["LangGraph: authorize,", "validate 85 answers"]),
        ("ml", "DCMFNet × 2", ["PyTorch, 105 features", "11 modalities, pos + neg"]),
        ("ml", "Reference levels", ["percentile vs 20k", "synthetic profiles"]),
        ("llm", "Gemini 3.5", ["Flash-Lite, async", "explanation"]),
        ("safety", "Number check", ["exact scores and", "percentiles only"]),
        ("client", "Result in chat", ["polled via /latest,", "levels + follow-ups"]),
    ])
    out = c.box(1760, 760, 200, 140, "client", "Validated SSE", ["validated_content,", "evidence, done", "→ chat UI"])
    for end in ends:
        ex, ey, ew, eh = end
        c.arrow([(ex + ew, ey + eh / 2), (1745, ey + eh / 2), (1745, 830), (1756, 830)])
    c.arrow([(1810, 446), (1810, 470), (1700, 470), (1700, 496)])

    c.box(40, 1160, 1920, 72, "monitor", "Monitoring (aggregates only, no message text)",
          ["live LLM judge Gemini 3.5 Flash (groundedness, correctness) · input drift z-score + "
           "per-question Monte Carlo tests (BH-FDR) · OOD: surprise + Mahalanobis · "
           "routing, guardrail and latency counters"])
    c.banner(40, 1250, 1920, 52,
             "The LLM never calculates risk, changes model outputs or invents citations.")
    return c


def ingestion_flow():
    """Build the offline evidence-ingestion diagram."""
    c = Canvas(2000, 1000, "Bodhica — Evidence Ingestion Flow",
               "Offline build of the research corpus and Qdrant index; abstracts only, "
               "no PDF text is indexed")
    w, h = 270, 132
    c.group(40, 130, 1920, 190, "Source selection")
    pdfs = c.box(64, 160, w, h, "client", "Research PDFs", ["data/Research Papers/",
                                                             "supplied by the researcher",
                                                             "identification only"])
    discover = c.box(374, 160, w, h, "api", "PDF discovery", ["rag_discover_pdfs.py",
                                                              "pypdf: DOI from page 1",
                                                              "no text indexed"])
    esearch = c.box(684, 160, w, h, "store", "NCBI ESearch", ["E-utilities API",
                                                             "DOI → PubMed ID",
                                                             "via curl"])
    manifest = c.box(994, 160, w, h, "safety", "Approved manifest", ["21 PMIDs + topics",
                                                                    "quality appraisals",
                                                                    "reviewer + date"])
    gold = c.box(1304, 160, w, h, "safety", "Claim catalog", ["curated claim support",
                                                             "hash-locked to corpus",
                                                             "gold benchmark sets"])
    c.right(pdfs, discover)
    c.right(discover, esearch)
    c.right(esearch, manifest)
    c.right(manifest, gold)

    c.group(40, 380, 1920, 370, "rag_ingest.py", label_x=260)
    efetch = c.box(64, 410, w, h, "store", "NCBI EFetch", ["E-utilities, XML", "PubmedArticle records",
                                                          "retraction metadata"])
    parse = c.box(374, 410, w, h, "api", "XML parsing", ["xml.etree.ElementTree",
                                                         "title, authors, DOI, date",
                                                         "labelled abstract sections"])
    admit = c.box(684, 410, w, h, "safety", "Admission checks", ["approved + appraisal passed",
                                                                "not retracted",
                                                                "retraction check ≤ 14 days"])
    chunk = c.box(994, 410, w, h, "retrieval", "Chunking", ["document: 1 per abstract",
                                                            "hierarchical: ≤ 300 tokens,",
                                                            "~30 overlap, sentence cuts"])
    tokens = c.box(1304, 410, w, h, "retrieval", "Token counting", ["MedCPT article",
                                                                    "tokenizer (Hugging Face)",
                                                                    "512-token limit"])
    c.arrow([(1069, 292), (1069, 340), (199, 340), (199, 406)])
    c.right(efetch, parse)
    c.right(parse, admit)
    c.right(admit, chunk)
    c.right(chunk, tokens)

    dense = c.box(374, 590, w, h, "retrieval", "Dense embeddings", ["MedCPT Article Encoder",
                                                                   "CLS pooling, 768-d",
                                                                   "title + text pairs"])
    sparse = c.box(684, 590, w, h, "retrieval", "Sparse BM25", ["local BM25 index",
                                                               "k1 = 1.2, b = 0.75",
                                                               "Qdrant sparse vectors"])
    qdrant = c.box(994, 590, w, h, "store", "Qdrant collections", ["qdrant-client, embedded",
                                                                   "document: 21 passages",
                                                                   "hierarchical: 39 passages"])
    pins = c.box(1304, 590, w, h, "safety", "Corpus manifest", ["rag_corpus_manifest.json",
                                                               "encoder SHA-256 pins",
                                                               "immutable versions"])
    c.arrow([(1439, 542), (1439, 566), (509, 566), (509, 586)])
    c.right(dense, sparse)
    c.right(sparse, qdrant)
    c.right(qdrant, pins)

    runtime = c.box(1640, 470, 296, 180, "api", "Runtime use", ["ResearchRuntime loads the",
                                                               "hierarchical collection,",
                                                               "MedCPT Query Encoder and",
                                                               "claim catalog; refuses on",
                                                               "hash or freshness mismatch"])
    c.arrow([(1574, 656), (1610, 656), (1610, 560), (1636, 560)])
    c.arrow([(1574, 226), (1788, 226), (1788, 466)], "claims")

    c.box(40, 790, 1920, 84, "monitor", "Evaluation",
          ["rag_general_benchmark.py on 19 gold questions: Recall@5 1.0, nDCG@5 0.95 "
           "(hierarchical) · cross-encoder rerankers (MedCPT, MiniLM) benchmarked and rejected",
           "Shipped to Modal: data/indexes/models, qdrant/ and the corpus manifest "
           "(deployment/modal_app.py)"])
    c.banner(40, 900, 1920, 56,
             "Only PubMed abstracts from approved, appraised, non-retracted sources are indexed.")
    return c


def render(name, canvas, png):
    """Write the SVG and, if requested, a PNG screenshot made with headless Chrome."""
    svg_path = OUT / f"{name}.svg"
    svg_path.write_text(canvas.svg(), encoding="utf-8")
    print(f"Saved {svg_path.relative_to(ROOT)}")
    if png:
        if not shutil.which(CHROME) and not Path(CHROME).exists():
            raise SystemExit("Google Chrome is required for PNG export")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--screenshot={OUT / (name + '.png')}",
                        f"--window-size={canvas.width},{canvas.height}",
                        svg_path.as_uri()], check=True, capture_output=True)
        print(f"Saved {(OUT / (name + '.png')).relative_to(ROOT)}")


def main():
    """Run the command-line workflow: render both architecture diagrams."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-png", action="store_true")
    args = parser.parse_args()
    render("clinical-risk-ai-query-flow", query_flow(), not args.no_png)
    render("clinical-risk-ai-ingestion-flow", ingestion_flow(), not args.no_png)


if __name__ == "__main__":
    main()

import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path("/home/rxtxr/projects/agency-tycoon/.env")
if _env_path.exists():
    load_dotenv(_env_path)

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY", "")
TOGETHER_BASE_URL = "https://api.together.xyz/v1"

ROOT = Path(__file__).parent
KNOWLEDGE_DIR = ROOT / "knowledge"
WAVES_DIR = ROOT / "waves"
WIKI_HTML_DIR = ROOT / "wiki"
WIKI_OBSIDIAN_DIR = Path("/home/rxtxr/Dokumente/rxtxr/Agenturgeschichte")

CATEGORIES = [
    "agencies", "people", "eras", "work",
    "life", "technology", "philosophy", "scandals", "visuals",
]

CATEGORY_LABELS = {
    "agencies":   "Agenturen",
    "people":     "Personen",
    "eras":       "Epochen",
    "work":       "Arbeiten & Kampagnen",
    "life":       "Agenturleben",
    "technology": "Technik & Ausstattung",
    "philosophy": "Philosophie & Strömungen",
    "scandals":   "Skandale & Kontroversen",
    "visuals":    "Visuelles",
}

MODELS = {
    "archivar":      "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "historiker":    "deepseek-ai/DeepSeek-V3.1",
    "journalist":    "Qwen/Qwen3.5-397B-A17B",
    "bildredakteur": "deepseek-ai/DeepSeek-V3.1",
    "wiki_editor":   "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "verifier":      "deepseek-ai/DeepSeek-V3.1",
}

MAX_TOKENS = {
    "archivar":      3000,
    "historiker":    4000,
    "journalist":    4000,
    "bildredakteur": 3000,
    "wiki_editor":   3000,
    "verifier":      6000,
}

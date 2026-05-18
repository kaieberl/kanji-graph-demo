"""Create worksheet input from Japanese text and the kanji component graph.

The deterministic dry-run path extracts kanji and vocabulary from an input text.
With OPENAI_API_KEY set, the script can ask GPT-5.2 to turn that extracted
input into Markdown tables for a worksheet.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.main import DEFAULT_GRAPH_PATH, KanjiGraph


MODEL = "gpt-5.2"
REASONING = {"effort": "none"}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "worksheets"
PARTICLES = set("がをにへとでのもやかは")


@dataclass(frozen=True)
class WorksheetInput:
    explanations: str
    vocabulary: str


def extract_worksheet_input(text: str, graph: KanjiGraph, level: int) -> WorksheetInput:
    seen_kanji: set[str] = set()
    explanation_lines: list[str] = []
    vocabulary_lines: list[str] = []

    for index, char in enumerate(text):
        if char in seen_kanji:
            continue
        kanji_level = graph.get_level(char)
        if not 0 <= kanji_level <= level:
            continue

        seen_kanji.add(char)
        containing_word = extract_containing_word(text, index)
        vocabulary_lines.append(containing_word)

        _, reading_kun = graph.get_readings(char)
        reading_hints = _format_kunyomi_hints(char, reading_kun)
        similar_kanji = graph.get_similar_kanji(char, level_limit=level)
        warning = " ".join(f"!{item}" for item in similar_kanji)
        explanation_lines.append(" ".join(part for part in [reading_hints, containing_word, warning] if part))

    return WorksheetInput(
        explanations="\n".join(explanation_lines),
        vocabulary="\n".join(vocabulary_lines),
    )


def extract_containing_word(text: str, index: int) -> str:
    """Extract a compact example word around a kanji without a tokenizer."""
    start = index
    while start > 0 and _is_kanji(text[start - 1]):
        start -= 1

    end = index + 1
    while end < len(text) and _is_kanji(text[end]):
        end += 1

    okurigana_end = end
    while (
        okurigana_end < len(text)
        and _is_hiragana(text[okurigana_end])
        and text[okurigana_end] not in PARTICLES
        and okurigana_end - end < 2
    ):
        okurigana_end += 1

    word = text[start:okurigana_end]
    while len(word) > 1 and word[-1] in PARTICLES:
        word = word[:-1]
    return word


def _is_kanji(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def _is_hiragana(char: str) -> bool:
    return "\u3040" <= char <= "\u309f"


def _format_kunyomi_hints(kanji: str, readings: list[str]) -> str:
    if not readings:
        return kanji
    hints: list[str] = []
    for reading in readings:
        if "（" in reading and "）" in reading:
            hints.append(kanji + reading.split("（", 1)[1].split("）", 1)[0])
        else:
            hints.append(kanji)
    return "[" + " ".join(hints) + "]"


def generate_markdown_table(prompt: str) -> str:
    try:
        from dotenv import load_dotenv
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the LLM extras to generate tables: pip install -e '.[llm]'") from exc

    load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required unless --dry-run is used.")

    client = OpenAI()
    response = client.responses.create(
        model=MODEL,
        input=prompt,
        reasoning=REASONING,
    )
    return response.output_text.strip()


def build_explanation_prompt(worksheet_input: WorksheetInput) -> str:
    return f"""以下の日本語の単語を使って、最終的な表を作成してください。
角括弧[]で囲まれた単語や漢字については、最も一般的に使用されている単語のうちの1つを選んでください。
ビックリマーク(!)で示された似ている漢字を「注意」列に入れてください。

入力:
'''{worksheet_input.explanations}'''

表には「日本語」、「読み方」、「意味」、「使い方」、「注意」という列があります。
意味はドイツ語で書いてください。使い方の単語は Markdown リンクにし、リンク先にひらがなの読み方を入れてください。
例: [皆様](-みなさま)
"""


def build_vocabulary_prompt(worksheet_input: WorksheetInput) -> str:
    return f"""以下の日本語の単語を使って、最終的な表を作成してください。

入力:
'''{worksheet_input.vocabulary}'''

表には「日本語」、「読み方」、「意味」という列があります。
意味はドイツ語で書いてください。
"""


def write_outputs(worksheet_input: WorksheetInput, output_dir: Path, dry_run: bool) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        files = {
            "worksheet-explanations-input.txt": worksheet_input.explanations,
            "worksheet-vocabulary-input.txt": worksheet_input.vocabulary,
        }
    else:
        files = {
            "worksheet-explanations.md": generate_markdown_table(build_explanation_prompt(worksheet_input)),
            "worksheet-vocabulary.md": generate_markdown_table(build_vocabulary_prompt(worksheet_input)),
        }

    written: list[Path] = []
    for filename, content in files.items():
        path = output_dir / filename
        path.write_text(content + "\n", encoding="utf-8")
        written.append(path)
    return written


def compile_pdf(markdown_path: Path) -> Path:
    pdf_path = markdown_path.with_suffix(".pdf")
    template = REPO_ROOT / "out" / "japanese-template.tex"
    command = ["pandoc", str(markdown_path), "-o", str(pdf_path), f"--template={template}"]
    subprocess.run(command, check=True)
    return pdf_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-file", default=REPO_ROOT / "data" / "input_texts" / "test_input.txt", type=Path)
    parser.add_argument("--graph", default=DEFAULT_GRAPH_PATH, type=Path)
    parser.add_argument("--level", default=5, type=int)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Write deterministic LLM input only.")
    parser.add_argument("--pdf", action="store_true", help="Compile generated Markdown with pandoc.")
    args, overrides = parser.parse_known_args()

    for item in overrides:
        if "=" not in item:
            parser.error(f"unrecognized argument: {item}")
        key, value = item.split("=", 1)
        if key == "input_file":
            args.input_file = Path(value)
        elif key == "level":
            args.level = int(value)
        elif key == "output_dir":
            args.output_dir = Path(value)
        else:
            parser.error(f"unknown override: {key}")
    return args


def main() -> None:
    args = parse_args()
    graph = KanjiGraph(args.graph)
    text = args.input_file.read_text(encoding="utf-8")
    worksheet_input = extract_worksheet_input(text, graph, level=args.level)
    written = write_outputs(worksheet_input, args.output_dir, dry_run=args.dry_run)

    if args.pdf and not args.dry_run:
        written.extend(compile_pdf(path) for path in written if path.suffix == ".md")

    for path in written:
        print(path.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()

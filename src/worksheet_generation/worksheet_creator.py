import json
import os
import logging
from pathlib import Path
from typing import List
import subprocess

import hydra
from openai import OpenAI
from sudachipy import Dictionary, SplitMode
from omegaconf import DictConfig

from src.main import KanjiGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / 'out'
os.environ['OPENAI_API_KEY'] = (PROJECT_DIR / 'openai.txt').read_text().strip()

graph = KanjiGraph('data/kanji_digraph.gexf')


def get_kanji_data(kanjis: List[str] = None):
    """
    Make a list of all kanji in the graph, their components and similar kanji that are not in a lower (more difficult) level
    Write the list to a json file, e.g.: 伺,[亻,司],[飼,詞]
    """
    if not kanjis:
        kanjis = list(graph.G.nodes)
    kanji_list = []
    for kanji in kanjis:
        level = graph.get_level(kanji)
        if level >= 0:
            components, compounds, similar_kanji = graph.get_components_compounds_and_similar_kanji(kanji,
                                                                                                    level_limit=level)
            if len(components) > 0:
                kanji_list.append([kanji, components, compounds, similar_kanji])
    with open('kanji_list.csv', 'w', encoding='utf-8') as f:
        f.write('kanji,components,compounds,similar_kanji\n')
        for item in kanji_list:
            components_str = '"' + ','.join(item[1]) + '"' if item[1] else '""'
            compounds_str = '"' + ','.join(item[2]) + '"' if item[2] else '""'
            similar_kanji_str = '"' + ','.join(item[3]) + '"' if item[3] else '""'

            # Format as a single CSV line
            csv_line = f"{item[0]},{components_str},{compounds_str},{similar_kanji_str}"
            f.write(csv_line + '\n')


def request_gpt(user_message: str, model: str, tokens: int) -> json:
    client = OpenAI()
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": user_message},
        ],
        max_tokens=tokens,
        temperature=0.1
    )


def request_table_explanations(kanji_list: str):
    message = f"""以下の日本語の単語を使って、最終的な表を作成してください。各行は表の一行に対応します。
角括弧[]で囲まれた単語や漢字については、最も一般的に使用されている単語のうちの1つを選んでください。新しい単語を作り出さないでください。与えられた漢字を正確に同じようにコピーしてください。これらの単語については、「使い方」列に角括弧に続く単語を入れてください。
'''{kanji_list}'''
表には「日本語」、「読み方」、「意味」、「使い方」、「注意」という列があります。最初の列には私が渡した単語や漢字を、二列目にはふりがなの読み方を、三列目にはドイツ語の翻訳を、四列目には角括弧に続く単語を、最後の列にはビックリマーク(!)で示された、似ている漢字を入れてください。[選ばれた指定された単語]が提供された漢字の表記と正確に一致していることを確認してください。
使い方の単語の後に、先頭にダッシュを付けて、括弧内にひらがなの読み方を入れてください(-...)。そうして、マークダウンのリンクを作りなさい。例：[皆様](-みなさま)
例：
| 日本語   | 読み方        | 意味               | 使い方    |
|----------|--------------|------------------|-----------|---|
| 蔵       | くら          | Speicher         | [蔵書](-ぞうしょ)     |
| 皆       | みな          | Alle             | [皆様](-みなさま)      |"""
    response = request_gpt(message, "gpt-4-1106-preview", 300)
    return response.choices[0].message.content.strip()


def request_table_vocabs(kanji_list: str):
    message = f"""以下の日本語の単語を使って、最終的な表を作成してください。各行は表の一行に対応します。
'''{kanji_list}'''
表には「日本語」、「読み方」、「意味」という列があります。最初の列には私が渡した単語や漢字を、二列目にはふりがなの読み方を、三列目にはドイツ語の翻訳を入れてください。
例：
| 日本語   | 読み方        | 意味               |
|----------|--------------|------------------|
| 半蔵     | はんぞう      | Halbversteckt    |
| 皆       | みな          | Alle             |"""
    response = request_gpt(message, "gpt-4-1106-preview", 300)
    return response.choices[0].message.content.strip()


def compile_worksheet(input_file: Path):
    command = f"pandoc -F handle_furigana.py {OUTPUT_DIR / input_file} -o {OUTPUT_DIR / f'{input_file.stem}.pdf'} --template=japanese-template.tex"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()

    if process.returncode == 0:
        os.system(f"open {OUTPUT_DIR / input_file.stem}.pdf")
    else:
        raise Exception(error.decode('utf-8'))


@hydra.main(config_path="../../config", config_name="config")
def main(config: DictConfig):
    """
    Print all kanji in the graph that are in a certain level or lower, marked with * for ChatGPT to search for words.
    Also print kunyomi if available.

    Example usage:
    python3 worksheet_creator.py -i kanji_list.csv -l 10
    """
    input_file = config.input_file

    with open(input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    tokenizer = Dictionary().create()
    morphemes = tokenizer.tokenize(text, SplitMode.A)
    kanji_list_expl = ""
    kanji_list_vocab = ""
    for kanji in text:
        if 0 <= graph.get_level(kanji) <= int(config.level) and kanji not in kanji_list_vocab:
            # print word containing kanji
            for morpheme in morphemes:
                if kanji in morpheme.surface():
                    kanji_list_vocab += f'{morpheme.surface()}\n'
                    break
            _, reading_kun = graph.get_readings(kanji)
            # extract characters enclosed in brackets from first reading_kun
            if reading_kun:
                kanji_list_expl += "["
                try:
                    for i in range(len(reading_kun)):
                        kanji_list_expl += kanji + reading_kun[i].split('（')[1].split('）')[0] + (
                            ' ' if i < len(reading_kun) - 1 else ']')
                except IndexError:  # kunyomi without accompanying hiragana
                    # print(kanji)
                    kanji_list_expl += kanji + ']'
            common_word = graph.G.nodes[kanji]['common_word'] if 'common_word' in graph.G.nodes[kanji] else ''
            kanji_list_expl += f' {common_word}'
            similar_kanji = graph.get_similar_kanji(kanji, level_limit=config.level)
            kanji_list_expl += f'{" !".join(similar_kanji)}\n'

    logging.info(f"Kanji list with explanations:\n{kanji_list_expl}")
    logging.info(f"Kanji list with vocabs:\n{kanji_list_vocab}")
    # sys.exit(0) # only print kanji list, since gpt-4 still makes mistakes
    response = request_table_explanations(kanji_list_expl)
    logging.info(f"Response:\n{response}")
    response = [line for line in response.split('\n') if len(line) < 63 and line.count('|') == 6]
    response = '\n'.join(response)
    # write one version with explanations, one without
    with open(OUTPUT_DIR / f'vocab-{input_file.stem}-explanations.md', 'w', encoding='utf-8') as f:
        f.write(response)
    compile_worksheet(Path(f'vocab-{input_file.stem}-explanations.md'))
    response = request_table_vocabs(kanji_list_vocab)
    logging.info(f"Response:\n{response}")
    response = [line for line in response.split('\n') if len(line) < 55 and line.count('|') == 4]
    response = '\n'.join(response)
    with open(OUTPUT_DIR / f'vocab-{input_file.stem}-vocabs.md', 'w', encoding='utf-8') as f:
        f.write(response)
    compile_worksheet(Path(f'vocab-{input_file.stem}-vocabs.md'))


if __name__ == '__main__':
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir()
    main()

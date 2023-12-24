# create graph from the data scraped from the web
import csv
import json
import re
import unicodedata

import networkx as nx
from bs4 import BeautifulSoup


def extract_property(html, pattern):
    match = re.search(pattern, html)
    return match.group(1)


def extract_level(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = -1
    for tr in soup.find_all('tr'):
        if '級' in tr.get_text() and tr.find('th') is not None and tr.find('th').get_text() == '漢字検定':
            text = tr.get_text(strip=True)
            number = ''.join(filter(str.isdigit, text))
            # Normalize the number to ASCII
            result = unicodedata.normalize('NFKD', number)
            break
    return int(result)


def extract_readings(html, reading_type):
    soup = BeautifulSoup(html, 'html.parser')
    readings = []
    for th in soup.find_all('th'):
        if reading_type in th.get_text():
            # Get the number of readings from rowspan attribute, default to 1 if not found
            rowspan = int(th.get('rowspan', 1))
            current_tr = th.parent
            for _ in range(rowspan):
                td = current_tr.find('td')
                if td:
                    readings.append(td.get_text(strip=True))
                current_tr = current_tr.find_next_sibling('tr')
            break

    return str(readings)


def extract_components(html):
    soup = BeautifulSoup(html, 'html.parser')
    try:
        return soup.find_all('li')[1].get_text().split('＋')
    except IndexError:
        return []


def extract_strokes(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tr in soup.find_all('tr'):
        if '画数' in tr.get_text() and tr.find('th') is not None and tr.find('th').get_text() == '画数':
            text = tr.get_text(strip=True)
            # extract 1 from '画数１画（一１＋０）'
            text = text.split('画')[1]
            number = ''.join(filter(str.isdigit, text))
            # Normalize the number to ASCII
            result = unicodedata.normalize('NFKD', number)
            break
    return int(result)


def create_graph(data):
    G = nx.DiGraph()
    for item in data:
        kanji = extract_property(item['kanji'], r'「(.*?)」')
        level = extract_level(item['content1'])
        reading_on = extract_readings(item['content1'], '音')
        reading_kun = extract_readings(item['content1'], '訓')
        strokes = extract_strokes(item['content1'])
        if kanji not in G:
            G.add_node(kanji, level=level, reading_on=reading_on, reading_kun=reading_kun, strokes=strokes)
        else:
            G.nodes[kanji]['level'] = level
            if reading_on:
                G.nodes[kanji]['reading_on'] = reading_on
            if reading_kun:
                G.nodes[kanji]['reading_kun'] = reading_kun
            G.nodes[kanji]['strokes'] = strokes
        for component in extract_components(item['content2']):
            if component not in G:
                G.add_node(component, level=-1)  # mark as non-existent kanji
            G.add_edge(component, kanji)  # relationship is component -> kanji

    return G


def add_common_words(G):
    """
    add most commonly used word to each node
    Returns: the resulting graph
    """
    with open('data/common_words.txt', 'r', encoding='utf-8') as f:
        for level, line in enumerate(f):
            for pos, kanji in enumerate([node for node in G.nodes if G.nodes[node]['level'] == 7 - level]):
                G.nodes[kanji]['common_word'] = line.split(',')[pos].strip()
                # issue warning if kanji is not in word
                if kanji not in G.nodes[kanji]['common_word']:
                    print(f'Warning: {kanji} not in {G.nodes[kanji]["common_word"]}')
    return G


def add_words():
    """
    Add words to the graph and connect with kanji. Work in progress.
    """
    with open('data/common_words.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            for word in row[1:]:
                if word not in G:
                    G.add_node(word, level=-1, entity='word')
                for character in word:
                    G.add_edge(character, word)


def write_nodes_to_csv(G, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Id', 'Level', 'Reading_On', 'Reading_Kun', 'Strokes'])  # Header
        for node, attrs in G.nodes(data=True):
            writer.writerow([node, attrs.get('level', -1), attrs.get('reading_on', ''),
                             attrs.get('reading_kun', ''), attrs.get('strokes', -1)])


def write_edges_to_csv(G, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Source', 'Target'])  # Header
        for source, target in G.edges():
            writer.writerow([source, target])


if __name__ == "__main__":
    # read in all files and create a graph
    kanji_data = []
    for i in range(100, 11800, 100):
        with open(f'data/kanji_data_{i}.json', 'r', encoding='utf-8') as f:
            print(f'Reading file kanji_data_{i}.json')
            kanji_data.extend(json.load(f))
    G = create_graph(kanji_data)
    G = add_common_words(G)
    nx.write_gexf(G, 'data/kanji_digraph.gexf')
    write_nodes_to_csv(G, 'data/kanji_nodes.csv')
    write_edges_to_csv(G, 'data/kanji_edges.csv')
    print('Graph created')

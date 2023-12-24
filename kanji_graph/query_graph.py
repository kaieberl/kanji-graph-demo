import math

import networkx as nx
import matplotlib
from matplotlib import pyplot as plt
matplotlib.rcParams['font.sans-serif'] = 'Hiragino Sans GB'


def get_similar_kanji(kanji, G, depth=0, similar_kanji=None, previous_direction=None, depth_limit=0.9):
    if similar_kanji is None:
        similar_kanji = []
    similar_kanji_set = set(similar_kanji)

    # Add depth limit to prevent infinite recursion
    if depth > depth_limit:
        return similar_kanji

    # components of the kanji (predecessors)
    for component in G.predecessors(kanji):
        if (component, depth) not in similar_kanji_set:
            if G.nodes[component]['level'] >= 0:
                similar_kanji.append((component, depth))
                similar_kanji_set.add((component, depth))
            # strokes = G.nodes[component]['strokes'] if 'strokes' in G.nodes[component] else 2
            commonality_penalty = math.tanh(len(list(G.successors(component))) / 100)
            if previous_direction != 'successor':
                get_similar_kanji(component, G, depth + commonality_penalty, similar_kanji, 'predecessor', depth_limit)

    # kanji that contain the kanji as component (successors)
    for compound in G.successors(kanji):
        if (compound, depth) not in similar_kanji_set:
            if G.nodes[compound]['level'] >= 0:
                similar_kanji.append((compound, depth))
                similar_kanji_set.add((compound, depth))
            # strokes = G.nodes[kanji]['strokes'] if 'strokes' in G.nodes[kanji] else 2
            commonality_penalty = math.tanh(len(list(G.successors(kanji))) / 100)
            if previous_direction != 'predecessor':
                get_similar_kanji(compound, G, depth + commonality_penalty, similar_kanji, 'successor', depth_limit)

    if depth == 0:
        similar_kanji.sort(key=lambda x: x[1])

    return similar_kanji


def get_similar_kanji_graph(kanji, G):
    similar_kanji = get_similar_kanji(kanji, G)
    similar_kanji_graph = nx.Graph()
    for item in similar_kanji:
        if item[0] not in similar_kanji_graph:
            similar_kanji_graph.add_edge(item[0], kanji, depth=1 / (item[1] + 0.1))
    return similar_kanji_graph


if __name__ == "__main__":
    # load graph
    G = nx.read_gexf('data/kanji_digraph.gexf')

    # Get similar kanji
    kanji = '持'
    similar_kanji = get_similar_kanji(kanji, G)
    # filter out kanji with depth > 1
    similar_kanji = [item for item in similar_kanji if item[1] <= 1]
    # order by depth
    similar_kanji = sorted(similar_kanji, key=lambda x: x[1])
    # remove duplicates and original kanji, preserving order
    similar_kanji = [item[0] for item in similar_kanji if item[0] != kanji and item[0] not in similar_kanji]

    SG = get_similar_kanji_graph(kanji, G)
    # plot graph
    nx.draw(SG, with_labels=True, pos=nx.spring_layout(SG, weight='depth', k=0.5, iterations=50))
    plt.show()
    print(similar_kanji)
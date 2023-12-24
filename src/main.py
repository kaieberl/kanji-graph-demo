from typing import List

import networkx as nx


class KanjiGraph:
    def __init__(self, path):
        self.G = nx.read_gexf(path)

    def get_components(self, kanji: str) -> List[str]:
        return list(self.G.predecessors(kanji))

    def get_readings(self, kanji: str) -> (List[str], List[str]):
        reading_on = self.G.nodes[kanji]['reading_on']
        reading_kun = self.G.nodes[kanji]['reading_kun']
        # convert "['a', 'b']" to ["a", "b"]
        reading_on = reading_on[1:-1].replace("'", "").split(', ') if len(reading_on) > 2 else []
        reading_kun = reading_kun[1:-1].replace("'", "").split(', ') if len(reading_kun) > 2 else []
        return reading_on, reading_kun

    def get_similar_kanji_deep(self, kanji, depth=0, similar_kanji=None, height=0, level_limit=0, depth_limit=2) -> List[str]:
        if similar_kanji is None:
            similar_kanji = []
        similar_kanji_set = set(similar_kanji)

        if depth > depth_limit:
            return similar_kanji

        # components of the kanji (predecessors)
        for component in self.G.predecessors(kanji):
            if (component, depth) not in similar_kanji_set:
                if self.G.nodes[component]['level'] >= level_limit:
                    similar_kanji.append((component, depth, height - 1))
                    similar_kanji_set.add((component, depth, height - 1))
                self.get_similar_kanji_deep(component, depth + 1, similar_kanji, height - 1, level_limit, depth_limit)

        # kanji that contain the kanji as component (successors)
        for compound in self.G.successors(kanji):
            if (compound, depth, height) not in similar_kanji_set:
                if self.G.nodes[compound]['level'] >= level_limit:
                    similar_kanji.append((compound, depth, height + 1))
                    similar_kanji_set.add((compound, depth, height + 1))
                self.get_similar_kanji_deep(compound, depth + 1, similar_kanji, height + 1, level_limit, depth_limit)

        return similar_kanji

    def get_similar_kanji(self, kanji: str, level_limit: int) -> (str, int, int):
        # TODO: use information about position of the component in the kanji
        components = self.get_components(kanji)
        if len(components) == 0:
            return []
        components.sort(key=lambda x: self.G.nodes[x]['strokes'] if 'strokes' in self.G.nodes[x] else 1, reverse=True)
        similar_kanji = list(self.get_successors(components[0], kanji))
        return [item for item in similar_kanji if self.G.nodes[item]['level'] >= level_limit][0:min(2, len(similar_kanji))]

    def get_components_compounds_and_similar_kanji(self, kanji: str, level_limit: int):
        components = self.get_components(kanji)
        if len(components) == 0:
            return [], [], []
        compounds = list(self.G.successors(kanji))
        components.sort(key=lambda x: self.G.nodes[x]['strokes'] if 'strokes' in self.G.nodes[x] else 1, reverse=True)
        # filter out kanji with level < level_limit
        similar_kanji = list(self.get_successors(components[0], kanji))
        similar_kanji = [item for item in similar_kanji if self.G.nodes[item]['level'] >= level_limit]
        return components, compounds, similar_kanji

    def get_successors(self, component, kanji):
        return set(self.G.successors(component)) - {kanji}

    def get_level(self, kanji: str) -> int:
        if kanji not in self.G:
            return -1
        return self.G.nodes[kanji]['level']


if __name__ == '__main__':
    # load graph
    graph = KanjiGraph('data/kanji_digraph.gexf')
    kanji = '時'

    # Get readings
    readings = graph.get_readings(kanji)
    print(readings)

    # Get components
    components = graph.get_components(kanji)
    print(components)

    # get component with hightest number of strokes
    components.sort(key=lambda x: graph.G.nodes[x]['strokes'] if 'strokes' in graph.G.nodes[x] else 1, reverse=True)

    # Get similar kanji and print readings
    for component in components:
        print(f'\n========= Component: {component} =========')
        similar_kanji = list(graph.get_successors(component, kanji))
        similar_kanji.sort(key=lambda x: graph.G.nodes[x]['level'], reverse=True)
        # if level is lower, print in green (10 is easiest, 1 is hardest)
        for item in similar_kanji:
            if graph.G.nodes[item]['level'] > graph.G.nodes[kanji]['level']:
                print(f'\033[92m{item}\033[0m: {graph.G.nodes[item]["reading_on"]}, {graph.G.nodes[item]["reading_kun"]}')
            elif graph.G.nodes[item]['level'] < graph.G.nodes[kanji]['level']:
                print(f'\033[91m{item}\033[0m: {graph.G.nodes[item]["reading_on"]}, {graph.G.nodes[item]["reading_kun"]}')
            else:
                print(item, graph.G.nodes[item]['reading_on'], graph.G.nodes[item]['reading_kun'])

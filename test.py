def DFS(G, v, seen=None, path=None):
    if seen is None: seen = []
    if path is None: path = [v]

    seen.append(v)

    paths = []
    for t in G[v]:
        if t not in seen:
            t_path = path + [t]
            paths.append(tuple(t_path))
            paths.extend(DFS(G, t, seen[:], t_path))
    return paths


def convert(graph):
    adj = {i['id']: [] for i in graph['nodeDataArray']}  # список смежности
    for a in graph['linkDataArray']:
        adj[a['from']].append(a['to'])
    return adj


def convert_inverted(graph):
    adj = {i['id']: [] for i in graph['nodeDataArray']}  # список смежности
    for a in graph['linkDataArray']:
        adj[a['to']].append(a['from'])
    return adj


def get_weights(graph):
    weights = {}
    for a in graph['linkDataArray']:
        weight = int(a['text'])
        weights[(a['from'], a['to'])] = weight
    return weights


def get_queue3(graph):
    g = convert(graph)
    weights = get_weights(graph)
    path_values = {}
    for w in g:
        all_paths = DFS(g, w)
        max_path = 0
        for p in all_paths:
            prev = w
            path_len = 0
            for v in p[1:]:
                weight = weights[(prev, v)]
                prev = v
                path_len += weight
            if path_len > max_path:
                max_path = path_len
        path_values[w] = max_path

    def sort_key(w):
        return path_values[w]

    return sorted(list(g.keys()), key=sort_key, reverse=True)


def get_queue6(graph):
    g = convert(graph)
    path_values = {}
    for w in g:
        all_paths = DFS(g, w)
        max_path = max(len(p) for p in all_paths)
        path_values[w] = max_path

    def sort_key(w):
        return path_values[w]

    return sorted(list(g.keys()), key=sort_key, reverse=True)


def get_queue11(graph):
    g = convert_inverted(graph)
    path_values = {}
    for w in g:
        all_paths = DFS(g, w)
        max_path = max(len(p) for p in all_paths) if all_paths else 0
        path_values[w] = max_path

    def sort_key(w):
        return len(g[w]) * 1000 + path_values[w]

    return sorted(list(g.keys()), key=sort_key, reverse=True)


import json

g = {"class": "go.GraphLinksModel", "nodeKeyProperty": "id",
     "nodeDataArray": [
         {"id": 1, "text": "w1 (4)"},
         {"id": 2, "text": "w3 (5)"},
         {"id": 3, "text": "w4 (5)"}],
     "linkDataArray":
         [{"from": 1, "to": 2, "text": 1},
          {"from": 1, "to": 3, "text": 7},
          ]}
print(get_queue3(g))

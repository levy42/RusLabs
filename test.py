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


def render_diagram_ganta(diagram):
    s = ""
    for p, tasks in diagram.items():
        s += '\nP{:3s} | '.format(p)
        for t in tasks:
            if t[3]:
                s += " " * t[3] * 4
            s += str(t[0])
            s += " " * t[1] * 4
            if t[2]:
                s += "->{:2s}".format(str(t[2]))
        s += '\n     | '
        for t in tasks:
            if t[3]:
                s += "...." * t[3]
            s += '___:' * (t[1] - 1) + '___|'
            if t[2]:
                s += "->->" * t[4]
    return s


def create_ganta_diagram(task_graph, system_graph):
    # # generate P queue
    # p_g = convert(system_graph)
    # p_links = {p: len(p_g[p]) for p in p_g}
    # p_queue = sorted(p_g.keys(), key=lambda x: p_links[x])
    #
    # # generate Tasks queue
    # t_g = convert(task_graph)
    # t_w = get_weights(t_g)
    # t_queue = task_graph.queue
    #
    # diagram = {p for p in p_g}

    # (task, ticks, send_to, wait_ticks, send_ticks)
    return {
        '1': [(1, 5, None, 0, 1), (2, 5, None, 0, 1)],
        '2': [(3, 2, 2, 0, 1), (4, 7, None, 0, 1)],
        '3': [(5, 8, None, 3, 1)]
    }


print(render_diagram_ganta(create_ganta_diagram(None, None)))

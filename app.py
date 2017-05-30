from datetime import datetime
import json

from flask import Flask
from flask import render_template
from flask_sqlalchemy import SQLAlchemy
from flask import make_response
from flask import request
from flask import redirect
from flask import url_for

app = Flask(__name__)
app.config.from_mapping(SECRET_KEY='secret',
                        SQLALCHEMY_DATABASE_URI='sqlite:///app.db')
db = SQLAlchemy(app)


# Models

class GraphError(object):
    def __init__(self, cause='У графі знайдено цикли!'):
        self.cause = cause

    def __repr__(self):
        return 'Невалідний граф. %s' % self.cause


class SendDataType():
    MESSAGE = 'Пересилка повідомлень'
    CONVEY = 'Конвеєризація пересилок пакетами'


class TaskGraph(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    queue = db.Column(db.String)
    data = db.Column(db.String)


class CSGraph(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    data = db.Column(db.String)


class Parameters(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    link_number = db.Column(db.Integer, default=3)
    is_io = db.Column(db.Boolean, default=True)
    link_duplex = db.Column(db.Boolean, default=False)
    send_type = db.Column(db.String, default=SendDataType.MESSAGE)
    packet_length = db.Column(db.Integer, default=64)


db.create_all()


@app.context_processor
def context():
    return dict(render_ganta=render_diagram_ganta)


# views

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/task-graph/')
def task_graph():
    graphs = TaskGraph.query.all()
    return render_template('task_graph.html', graphs=graphs)


@app.route('/cs-graph/')
def cs_graph():
    graphs = CSGraph.query.all()
    return render_template('graph_cs.html', graphs=graphs)


@app.route('/statistics/')
def statistics():
    return render_template('statistics.html')


@app.route('/task-graph/', methods=['GET', 'POST'])
@app.route('/task-graph/<id>/', methods=['GET', 'POST'])
def save_task_graph(id=None):
    graph = None
    if id:
        graph = TaskGraph.query.get(id)
    if request.method == 'GET':
        return render_template('task_graph_redactor.html', graph=graph)
    if request.method == 'POST':
        if not id:
            graph = TaskGraph()
            graph.created_at = datetime.now()
        graph.name = request.form.get('name') or 'Граф без роду без імені'
        graph.updated_at = datetime.now()
        graph.data = request.form.get('graph')
        graph_data = json.loads(graph.data)
    try:
        if graph_has_cycle(graph_data):
            return render_template('task_graph_redactor.html', graph=graph,
                                   error=GraphError())
        if validate_and_format_graph(graph_data):
            graph.data = json.dumps(graph_data)
        else:
            return render_template('task_graph_redactor.html', graph=graph,
                                   error=GraphError(cause="Не валідний граф"))
    except Exception as e:
        print("Failed to check graph cycles. Error %s" % e)
    db.session.add(graph)
    db.session.commit()
    return redirect(url_for('save_task_graph', id=graph.id))


@app.route('/task-graph/<id>/generate-queue')
def generate_queue(id):
    graph = TaskGraph.query.get(id)
    queue_type = int(request.args.get('queue_type', 3))
    queue = None
    g = json.loads(graph.data)
    if queue_type == 3:
        queue = get_queue3(g)
    if queue_type == 6:
        queue = get_queue6(g)
    if queue_type == 11:
        queue = get_queue11(g)

    def get_name(id):
        v = [i for i in g['nodeDataArray'] if i['id'] == id][0]
        return v['text'].split('(')[0][:-1]

    queue = [get_name(v) for v in queue]

    graph.queue = json.dumps(queue)
    db.session.add(graph)
    db.session.commit()

    return render_template('task_graph_redactor.html', graph=graph,
                           queue=queue)


@app.route('/task-graph/<id>/download/')
def download_task_graph(id):
    graph = TaskGraph.query.get(id)
    response = make_response(graph.data)
    response.headers[
        "Content-Disposition"] = "attachment; filename=%s.json" % graph.name
    return response


@app.route('/task-graph/<id>/delete')
def delete_task_graph(id):
    graph = TaskGraph.query.get(id)
    if graph:
        db.session.delete(graph)
        db.session.commit()
    return redirect(url_for('task_graph'))


@app.route('/cs-graph/save/', methods=['GET', 'POST'])
@app.route('/cs-graph/save/<id>/', methods=['GET', 'POST'])
def save_cs_graph(id=None):
    graph = None
    if id:
        graph = CSGraph.query.get(id)
    if request.method == 'GET':
        return render_template('cs_graph_redactor.html', graph=graph)
    if request.method == 'POST':
        if not id:
            graph = CSGraph()
            graph.created_at = datetime.now()
        graph.name = request.form.get('name') or 'Граф без роду без імені'
        graph.updated_at = datetime.now()
        graph.data = request.form.get('graph')
        graph_data = json.loads(graph.data)
        try:
            if check_connected(graph_data):
                return render_template('cs_graph_redactor.html', graph=graph,
                                       error=GraphError('Граф не звязний!'))
        except Exception:
            pass
    db.session.add(graph)
    db.session.commit()
    return redirect(url_for('save_cs_graph', id=graph.id))


@app.route('/cs-graph/<id>/download/')
def download_cs_graph(id):
    graph = CSGraph.query.get(id)
    response = make_response(graph.data)
    response.headers[
        "Content-Disposition"] = "attachment; filename=%s.json" % graph.name
    return response


@app.route('/cs-graph/<id>/delete')
def delete_cs_graph(id):
    graph = CSGraph.query.get(id)
    if graph:
        db.session.delete(graph)
        db.session.commit()
    return redirect(url_for('cs_graph'))


@app.route('/modeling/')
def modeling():
    return redirect(url_for('modeling_parameters'))


@app.route('/modeling/parameters/')
def modeling_parameters():
    parameters = Parameters.query.first()
    if request.args.get('link_number'):
        parameters.link_number = request.args.get('link_number', type=int)
        parameters.link_duplex = request.args.get('link_duplex', type=bool)
        parameters.is_io = request.args.get('is_io', type=bool)
        parameters.send_data_type = request.args.get('send_type', type=str)
        parameters.packet_length = request.args.get('packet_length', type=int)
        db.session.add(parameters)
        db.session.commit()
        return redirect(url_for('modeling_parameters'))
    return render_template('modeling_parameters.html',
                           parameters=parameters,
                           send_types=[SendDataType.CONVEY,
                                       SendDataType.MESSAGE])


@app.route('/modeling/ganta/', methods=['GET', 'POST'])
def modeling_ganta():
    if request.method == 'GET':
        return render_template('modeling_ganta.html')
    else:
        task_graph_id = request.form.get('task_graph')
        system_graph_id = request.form.get('system_graph')
        task_graph = TaskGraph.query.get(task_graph_id)
        system_graph = CSGraph.query.get(system_graph_id)
        diagram = create_ganta_diagram(task_graph, system_graph)
        return render_template('modeling_ganta.html', diagram=diagram)


@app.route('/modeling/statistics/')
def modeling_statistics():
    return render_template('modeling_statistics.html')


@app.route('/help')
def help():
    return render_template('help.html')


# tools

def create_ganta_diagram(task_graph, system_graph):
    pass


def graph_has_cycle(graph):
    g = {}
    for v in graph['nodeDataArray']:
        g[v['id']] = []
    for d in graph['linkDataArray']:
        g[d['from']].append(d['to'])

    vertex = list(g.keys())[0]
    cur_path = set()

    def is_cyclic(g, vertex):
        cur_path.add(vertex)
        for neighboor in g.get(vertex, []):
            if neighboor in cur_path:
                return True
            else:
                if neighboor in g and is_cyclic(g, neighboor):
                    return True
        cur_path.remove(vertex)
        return False

    return is_cyclic(g, vertex)


def check_connected(graph):
    n, m = len(graph['nodeDataArray']), len(
            graph['linkDataArray'])  # количество вершин и ребер в графе
    adj = {i['id']: [] for i in graph['nodeDataArray']}  # список смежности
    for a in graph['linkDataArray']:
        adj[a['from']].append(a['to'])
        adj[a['to']].append(a['from'])
    used = {i['id']: False for i in graph['nodeDataArray']}

    def dfs(v):
        if used[v]:
            return
        used[v] = True
        print(v + 1, end=' ')
        for w in adj[v]:
            dfs(w)

    dfs(graph['nodeDataArray'][0]['id'])
    for u in used.values():
        if not u:
            return True
    return False


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
    for a in graph['nodeDataArray']:
        weight = int(a['text'].split('(')[1][:-1])
        weights[a['id']] = weight
    return weights


def get_queue3(graph):
    g = convert(graph)
    weights = get_weights(graph)
    path_values = {}
    for w in g:
        all_paths = DFS(g, w)
        max_path = 0
        if not all_paths:
            max_path = weights[w]
        else:
            for p in all_paths:
                path_len = 0
                for v in p:
                    weight = weights[v]
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
        max_path = max(len(p) for p in all_paths) if all_paths else 0
        path_values[w] = max_path

    def sort_key(w):
        return path_values[w]

    return sorted(list(g.keys()), key=sort_key, reverse=True)


def get_queue11(graph):
    g = convert_inverted(graph)
    g_real = convert(graph)
    path_values = {}
    for w in g:
        all_paths = DFS(g, w)
        max_path = max(len(p) for p in all_paths) if all_paths else 0
        path_values[w] = max_path

    def sort_key(w):
        return (len(g[w]) + len(g_real[w])) * 1000 - path_values[w]

    return sorted(list(g.keys()), key=sort_key, reverse=True)


def validate_and_format_graph(g):
    for v in g['nodeDataArray']:
        try:
            if '(' not in v['text']:
                v['text'] += ' (1)'
            else:
                weight = int(v['text'].split(' (')[1][:-1])
        except Exception as e:
            return False
    for l in g['linkDataArray']:
        try:
            if not l.get('text'):
                l['text'] = 'X'
            if l['text'] == 'X':
                l['text'] = 1
            else:
                weight = int(l['text'])
        except Exception as e:
            return False
    return True


def render_diagram_ganta(diagram):
    s = ""
    for p in diagram['procs']:
        for t in p['tasks']:
            s += t['name'] + " "
            if t.get('send_to'):
                s += "-> %s" % t['send_to']
            s += '\n'
            s += '-' * t['ticks'] + '\n'


if __name__ == '__main__':
    app.run(port=5001)

from datetime import datetime
import json

from flask import Flask
from flask import render_template
from flask_sqlalchemy import SQLAlchemy
from flask import make_response
from flask import request
from flask import redirect
from flask import url_for
import time

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

    def get_data(self):
        return json.loads(self.data)

    def get_queue(self):
        return json.loads(self.queue)


class CSGraph(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)
    data = db.Column(db.String)

    def get_data(self):
        return json.loads(self.data)


class Parameters(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    link_number = db.Column(db.Integer, default=3)
    is_io = db.Column(db.Boolean, default=True)
    link_duplex = db.Column(db.Boolean, default=False)
    send_type = db.Column(db.String, default=SendDataType.MESSAGE)
    packet_length = db.Column(db.Integer, default=64)


db.create_all()


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


@app.route('/task-graph/new/', methods=['GET', 'POST'])
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

    graph.queue = json.dumps(queue)
    db.session.add(graph)
    db.session.commit()

    queue = [get_name(v) for v in queue]

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
            if validate_and_format_graph(graph_data, system_graph=True):
                graph.data = json.dumps(graph_data)
            else:
                return render_template('cs_graph_redactor.html', graph=graph,
                                       error=GraphError('Граф не валідний!'))
            if check_connected(graph_data):
                return render_template('cs_graph_redactor.html', graph=graph,
                                       error=GraphError('Граф не звязний!'))
        except Exception as e:
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
    diagram = None
    if request.method == 'POST':
        task_graph_id = request.form.get('task_graph')
        system_graph_id = request.form.get('system_graph')
        variant = request.form.get('variant', type=int, default=3)
        task_graph = TaskGraph.query.get(task_graph_id)
        system_graph = CSGraph.query.get(system_graph_id)
        diagram = create_ganta_diagram(task_graph, system_graph, variant)
    return render_template('modeling_ganta.html', diagram=diagram,
                           task_graphs=TaskGraph.query.all(),
                           system_graphs=CSGraph.query.all())


@app.route('/modeling/statistics/')
def modeling_statistics():
    return render_template('modeling_statistics.html')


@app.route('/help')
def help():
    return render_template('help.html')


# tools

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


def convert(graph, arrow=True):
    adj = {i['id']: [] for i in graph['nodeDataArray']}  # список смежности
    for a in graph['linkDataArray']:
        adj[a['from']].append(a['to'])
        if not arrow:
            adj[a['to']].append(a['from'])
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


def get_edge_weights(graph):
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


def validate_and_format_graph(g, system_graph=False):
    renames = {}
    for v in g['nodeDataArray']:
        try:
            if not system_graph:
                if '(' not in v['text']:
                    v['text'] += ' (1)'
                    weight = 1
                else:
                    weight = int(v['text'].split('(')[1][:-1])
                v['weight'] = weight
            old_id = v['id']
            v['id'] = v['text'].split('(')[0].strip()
            renames[old_id] = v['id']
        except Exception as e:
            return False
    for l in g['linkDataArray']:
        l['to'] = renames[l['to']]
        l['from'] = renames[l['from']]
        if not system_graph:
            try:
                if not l.get('text'):
                    l['text'] = 'X'
                if l['text'] == 'X':
                    l['text'] = '1'
                else:
                    weight = int(l['text'])
            except Exception as e:
                return False
    return True


def create_ganta_diagram(task_graph, system_graph, variant=4):
    model = Model(task_graph, system_graph, variant=variant)
    model.plan()
    model.run()
    return model.render_diagram_ganta()


class Tick(object):
    def __init__(self, task=None, sends=[]):
        self.task = task
        self.sends = sends  ## [(task, proc)...]


class Data(object):
    def __init__(self, task_from, task_to, dest_proc, size):
        self.task_from = task_from
        self.task_to = task_to
        self.size = size
        self.path = []
        self.current = 0
        self.dest_proc = dest_proc
        self.next = None
        self.progress = 0


class Proc(object):
    def __init__(self, name, tasks, model=None):
        self.tasks = tasks
        self.ticks = 0
        self.log = []
        self.state = None
        self.name = name
        self.data = []
        self.data_tasks = []
        self.data_to_send = []
        self.current_task = None
        self.current_task_index = None
        self.links = {}
        self.finish = False
        self.model = model
        self.new_data = []

    def set_links(self, procs_names):
        self.links = {p: True for p in procs_names}

    def receive_data(self, data):
        print("Data receive from: task %s task to %s  dest %s on proc %s" % (
            data.task_from, data.task_to, data.dest_proc, self.name))
        self.new_data.append(data)

    def refresh_data(self):
        for d in self.new_data:
            self.data.append(d)
            self.data_tasks.append(d.task_from)
            if d.dest_proc != self.name:
                self.data_to_send.append(d)
                d.progress = 0
                d.next = d.path[d.current + 1]
        self.new_data = []

    def send_data(self, procs):
        sends = []
        for data in self.data_to_send:
            # if data in self.new_data:
            #     continue
            if self.links[data.next]:
                if self.model.variant == 4 and not self.model.tasks[
                    data.task_to].is_ready_to_receive():
                    continue
                print("Send data from %s to %s" % (
                    self.name, procs[data.path[data.current + 1]].name))
                self.links[data.next] = False
                data.progress += 1
                sends.append((data.task_to, data.next))
                if data.progress == data.size:
                    data = self.data_to_send.pop(0)
                    data.current += 1
                    procs[data.path[data.current]].receive_data(data)
        for l in self.links:
            self.links[l] = True

        return sends


class Task(object):
    def __init__(self, name, time, proc, data_size=1):
        self.state = None
        self.name = name
        self.time = time
        self.ticks = 0
        self.data_size = data_size
        self.proc = proc
        self.parents = []
        self.children = []

    def set_connected(self, parents, children):
        self.parents = parents
        self.children = children

    def is_ready_to_submit(self):
        if self.state == 'running': return True
        for p in self.parents:
            if p.name not in self.proc.data_tasks:
                return False
        self.state = 'running'
        return True

    def is_ready_to_receive(self):
        for p in self.parents:
            if p.state != 'finish':
                return False
        return True


class Model(object):
    def __init__(self, task_graph, system_graph, duplex=True, variant=4):
        # generate P queue

        self.task_queue = task_graph.get_queue()
        self.variant = variant
        task_graph = task_graph.get_data()
        system_graph = system_graph.get_data()
        self.duplex = True
        self.p_g = convert(system_graph, arrow=False)
        self.p_links = {p: len(self.p_g[p]) for p in self.p_g}
        self.p_queue = sorted(list(self.p_g.keys()),
                              key=lambda x: self.p_links[x] * 1000 - hash(x),
                              reverse=True)

        # generate Tasks queue
        self.task_graph = convert(task_graph)
        self.task_graph_inverted = convert_inverted(task_graph)
        self.p_ticks = {p: [] for p in self.p_g}
        if not self.task_queue:
            self.task_queue = get_queue3(task_graph)

        self.task_proc_map = {}
        self.proc_task_map = {}

        self.task_progress = {t: 0 for t in self.task_graph}
        self.task_lens = get_weights(task_graph)

        self.data_weights = get_edge_weights(task_graph)

        self.nodes = {p: Proc(p, [], model=self) for p in self.p_g}
        self.tasks = {t: Task(t, self.task_lens[t], None) for t in
                      self.task_graph}

        for node in self.nodes.values():
            node.set_links(self.p_g[node.name])

        for t in self.tasks.values():
            children = [self.tasks[c] for c in self.task_graph[t.name]]
            parents = [self.tasks[par] for par in
                       self.task_graph_inverted[t.name]]
            t.set_connected(parents, children)

    def assign_task(self, t, p):
        self.task_proc_map[t] = p
        if self.proc_task_map.get(p):
            self.proc_task_map[p].append(self.tasks[t])
        else:
            self.proc_task_map[p] = [self.tasks[t]]
        self.tasks[t].proc = self.nodes[p]
        self.nodes[p].tasks.append(self.tasks[t])
        print("Assigned: task %s to %s proc" % (t, p))

    def assign_tasks(self):
        if self.variant == 4:
            self.assign4()
        else:
            self.assign3()

    def assign3(self):
        for t in self.task_queue:
            self.assign_task(t, self.p_queue[0])
            self.p_queue.append(self.p_queue.pop(0))

    def assign4(self):
        for t in self.task_queue:
            assigned = False
            if len(self.task_graph_inverted[t]):
                # proc = [p for p in self.p_queue if
                #         p in [self.task_proc_map.get(t1) for t1 in
                #               self.task_graph_inverted[t]]][0]
                parents = sorted(self.task_graph_inverted[t],
                                 key=lambda x: -self.data_weights[(x, t)])
                p_choices = [self.task_proc_map.get(t1) for t1 in
                             parents]
                g = p_choices[0]
                p_choices2 = self.p_g[g]
                p_choices.append(p_choices2)
                self.assign_task(t, g)
                assigned = True
                # for p in p_choices:
                #
                # for i, p in enumerate(self.p_queue):
                #     if p in p_choices:
                #         # proc = p
                #         # index = i
                #         self.assign_task(t, p)
                #         assigned = True
                #         break
            if not assigned:
                self.assign_task(t, self.p_queue[0])
                self.p_queue.append(self.p_queue.pop(0))

    def plan(self):
        self.assign_tasks()

    def run(self):
        to_continue = True
        ticks = 0
        while to_continue:
            self.tick()
            ticks += 1
            to_continue = False
            for t in self.tasks.values():
                if t.state != 'finish':
                    to_continue = True
        print('finish!!!')

    def tick(self):
        for node in sorted(self.nodes.values(), key=lambda x: x.name):
            self.proc_tick(node)
        for t in self.tasks.values():
            if t.state == 'tofinish':
                t.state = 'finish'
        print("tick")

    def create_data(self, task, task_to):
        data = Data(task.name, task_to.name, task_to.proc,
                    self.data_weights[(task.name, task_to.name)])
        data.path = self.get_path(task.proc.name, task_to.proc.name)
        data.dest_proc = task_to.proc.name
        print(
            "Data created: task %s, dest %s" % (
                task.name, task_to.proc.name))
        return data

    def get_path(self, proc1, proc2):
        if proc2 in self.p_g.get(proc1):
            return [proc1, proc2]
        pathes = DFS(self.p_g, proc1)
        min_path = None
        for p in pathes:
            if proc2 in p:
                if not min_path or len(min_path) > len(p):
                    min_path = p

        return min_path

    def proc_tick(self, proc):
        proc.ticks += 1
        tick = Tick()
        tick.sends = proc.send_data(self.nodes)
        proc.log.append(tick)
        if proc.tasks and not proc.finish:
            if not proc.current_task:
                proc.current_task = proc.tasks[0]
                proc.current_task_index = 0
            if proc.current_task.is_ready_to_submit():
                proc.current_task.ticks += 1
                tick.task = proc.current_task
                print("Task progress task %s progress %s" % (
                    proc.current_task.name, proc.current_task.ticks))
            if proc.current_task.ticks == proc.current_task.time:
                proc.current_task.state = 'tofinish'
                proc.current_task_index += 1
                if len(proc.tasks) > proc.current_task_index:
                    proc.current_task = proc.tasks[proc.current_task_index]
                else:
                    proc.current_task = 'finish'
                    proc.finish = True
                for c in tick.task.children:
                    proc.receive_data(self.create_data(tick.task, c))
        proc.refresh_data()

    def render_diagram_ganta(self):
        s = ""
        tact_len = 8  # only odd number
        for p in sorted(self.nodes.values(), key=lambda x: x.name):
            s += '\nP{:3s} | '.format(p.name)
            for t in p.log:
                if t.sends:
                    send_string = ''
                    for send in t.sends:
                        send_string += '%s>%s,' % send
                    s += '{:8s}'.format(send_string)
                else:
                    s += ' ' * tact_len
            s += '\n     | '
            for t in p.log:
                if t.sends:
                    s += '->' * (tact_len // 2)
                else:
                    s += ' ' * tact_len
            s += '\n     | '
            for t in p.log:
                if t.task:
                    s += '{:8s}'.format(t.task.name)
                else:
                    s += ' ' * tact_len
            s += '\n     | '
            for t in p.log:
                if t.task:
                    s += '_' * (tact_len - 1) + ':'
                else:
                    s += ' ' * tact_len

        return s


if __name__ == '__main__':
    app.run(port=5001)

# task_graph = TaskGraph()
# task_graph.data = '{"nodeDataArray": [{"loc": "124.99999999999997 115.99999999999997", "weight": 1, "text": "1(1)", "id": "1"}, {"loc": "303.9999999999997 127.99999999999996", "weight": 1, "text": "2(1)", "id": "2"}, {"loc": "285.00000000000006 -4.000000000000041", "weight": 3, "text": "3(3)", "id": "3"}], "linkDataArray": [{"to": "2", "from": "1", "points": [163.10891515556824, 126.76019990573005, 210.9822386061878, 118.14648753097244, 258.05072053799114, 121.33192295818428, 304.3473279174276, 136.12378934957857], "text": "1"}, {"to": "3", "from": "2", "points": [316.3478558309984, 128.0496537435894, 299.79845736378206, 94.97058140093993, 294.961773204198, 60.25451350426455, 301.64314528655376, 23.91382015364669], "text": "3"}], "class": "go.GraphLinksModel", "nodeKeyProperty": "id"}'
#
# cs_graph = CSGraph()
# cs_graph.data = '{"linkDataArray": [{"from": "1", "text": "", "points": [97.19881025342616, 40.12681659696665, 320.0000677265881, 43.794327008047546], "to": "2"}, {"from": "2", "text": "", "points": [330.0994389900072, 57.921143605014265, 330.09943899000706, 229.9999999999999], "to": "4"}, {"from": "4", "text": "", "points": [320.00001679571363, 244.04335395164063, 96.19886118430065, 245.87778965337387], "to": "3"}, {"from": "3", "text": "", "points": [86.16720872744115, 232.0000058911206, 87.03166925257318, 53.92113771389391], "to": "1"}], "nodeDataArray": [{"loc": "76.99999999999993 25.999999999999925", "text": "1", "weight": 1, "id": "1"}, {"loc": "319.99999999999994 29.999999999999957", "text": "2", "weight": 1, "id": "2"}, {"loc": "320.00000000000006 229.99999999999994", "text": "4", "weight": 1, "id": "4"}, {"loc": "76.00000000000009 232.00000000000023", "text": "3", "weight": 1, "id": "3"}], "class": "go.GraphLinksModel", "nodeKeyProperty": "id"}'
# task_graph.queue = ['1', '2', '3']
# try:
#     print(create_ganta_diagram(task_graph, cs_graph))
# except Exception as e:
#     import traceback
#
#     traceback.print_exc()
#     print(e)

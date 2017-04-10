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


@app.route('/task-graph/save/', methods=['GET', 'POST'])
@app.route('/task-graph/save/<id>/', methods=['GET', 'POST'])
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
        if check_connected(graph_data):
            return render_template('task_graph_redactor.html', graph=graph,
                                   error=GraphError('Граф не звязний!'))
    except Exception as e:
        print("Failed to check graph cycles. Error %s" % e)
    db.session.add(graph)
    db.session.commit()
    return redirect(url_for('save_task_graph', id=graph.id))


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


@app.route('/modeling/ganta/')
def modeling_ganta():
    return render_template('modeling_ganta.html')


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
        print(v + 1, end=' ')
        for w in adj[v]:
            dfs(w)

    dfs(graph['nodeDataArray'][0]['id'])
    for u in used.values():
        if not u:
            return True
    return False


if __name__ == '__main__':
    app.run(port=5001)

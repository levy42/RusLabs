from flask import Flask
from flask import render_template
from flask_sqlalchemy import SQLAlchemy
from flask import request
from flask import redirect
from flask import url_for

app = Flask(__name__)
app.config.from_mapping(SECRET_KEY='secret',
                        SQLALCHEMY_DATABASE_URI='sqlite:///app.db')
db = SQLAlchemy(app)


class SendDataType():
    MESSAGE = 'Пересилка повідомлень'
    CONVEY = 'Конвеєризація пересилок пакетами'


class TaskGraph(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String)
    datetime = db.Column(db.DateTime)
    data = db.Column(db.String)


class GraphCS(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String)
    datetime = db.Column(db.DateTime)
    data = db.Column(db.String)


class Parameters(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    link_number = db.Column(db.Integer, default=3)
    is_io = db.Column(db.Boolean, default=True)
    link_duplex = db.Column(db.Boolean, default=False)
    send_type = db.Column(db.String, default=SendDataType.MESSAGE)
    packet_length = db.Column(db.Integer, default=64)


db.create_all()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/task-graph/')
def task_graph():
    return render_template('task_graph.html')


@app.route('/graph-cs/')
def graph_ks():
    return render_template('graph_cs.html')


@app.route('/modeling/')
def modeling():
    return render_template('modeling.html')


@app.route('/statistics/')
def statistics():
    return render_template('statistics.html')


@app.route('/task-graph/create/', methods=['GET', 'POST'])
def create_task_graph():
    if request.method == 'GET':
        return render_template('create_task_graph.html')


@app.route('/task-graph/load/', methods=['GET', 'POST'])
def load_task_graph():
    if request.method == 'GET':
        return render_template('create_task_graph.html')


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


if __name__ == '__main__':
    app.run(port=5001)

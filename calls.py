#!/usr/bin/env python
import logging
import os
from json import dumps

from flask import Flask, g, Response, request
from neo4j import GraphDatabase

app = Flask(__name__, static_url_path='/static/')

url = os.getenv("NEO4J_URI", "bolt://localhost:7687")
username = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "Tien1389")
neo4jVersion = os.getenv("NEO4J_VERSION", "3")
database = os.getenv("NEO4J_DATABASE", "neo4j")

port = os.getenv("PORT", 8080)

driver = GraphDatabase.driver(url, auth=(username, password))


def get_db():
    if not hasattr(g, 'neo4j_db'):
        if neo4jVersion.startswith("4"):
            g.neo4j_db = driver.session(database=database)
        else:
            g.neo4j_db = driver.session()
    return g.neo4j_db


@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'neo4j_db'):
        g.neo4j_db.close()


@app.route("/")
def get_index():
    return app.send_static_file('index.html')


def serialize_city(city):
    return {
        'name': city['name']
    }


def serialize_location(location):
    return {
        'address': location['address'],
        'cell_site': location['cell_site'],
        'city': location['city'],
        'state': location['state']
    }


def serialize_call(call):
    return {
        'id': call['id'],
        'duration': call['duration'],
        'start': call['start'],
        'end': call['end']
    }


def serialize_person(person):
    return {
        'number': person['number'],
        'last_name': person['last_name'],
        'full_name': person['full_name'],
        'first_name': person['first_name']
    }


@app.route("/load_city_option")
def load_city_option():
    db = get_db()
    results = db.read_transaction(lambda tx: list(tx.run("MATCH (c:CITY) "
                                                         "RETURN c"
                                                         )))
    return Response(dumps([serialize_city(record['c']) for record in results]),
                    mimetype="application/json")


@app.route("/load_location_option")
def load_location_option():
    db = get_db()
    results = db.read_transaction(lambda tx: list(tx.run("MATCH (location:LOCATION) "
                                                         "RETURN location"
                                                         )))
    return Response(dumps([serialize_location(record['location']) for record in results]),
                    mimetype="application/json")


@app.route("/graph")
def get_graph():
    db = get_db()
    results = db.read_transaction(lambda tx: list(tx.run('MATCH (person:PERSON)-[:KNOWS]->(knownPerson:PERSON) '
                                                         'RETURN person.full_name as movie, collect(knownPerson.full_name) as cast '
                                                         'LIMIT $limit', {
                                                             'limit': request.args.get("limit",
                                                                                       20)})))
    nodes = []
    rels = []
    i = 0

    for record in results:
        nodes.append({"title": record["movie"], "label": "movie"})
        target = i
        i += 1
        for name in record['cast']:
            actor = {"title": name, "label": "actor"}
            try:
                source = nodes.index(actor)
            except ValueError:
                nodes.append(actor)
                source = i
                i += 1
            rels.append({"source": source, "target": target})
    return Response(dumps({"nodes": nodes, "links": rels}),
                    mimetype="application/json")


@app.route("/search", methods=["POST"])
def get_search():
    db = get_db()

    bodyJson = request.get_json()

    cityName = bodyJson["cityName"]
    locationAddress = bodyJson["locationAddress"]
    callStart = bodyJson["callStart"]
    callEnd = bodyJson["callEnd"]

    results = db.read_transaction(
        lambda tx: list(tx.run('MATCH (call:CALL)-[:LOCATED_IN]->(location:LOCATION)-[:HAS_CITY]->(city:CITY)'
                               ' WHERE city.name="' + cityName + '" AND location.address ="' + locationAddress +
                               '" AND call.start >= ' + callStart + ' AND call.end< ' + callEnd +
                               ' RETURN call'
                               )))
    return Response(dumps([serialize_call(record['call']) for record in results]),
                    mimetype="application/json")


@app.route("/call/<id>")
def get_call(id):
    db = get_db()
    result = db.read_transaction(
        lambda tx: list(tx.run('MATCH (caller:PERSON)-[mc:MADE_CALL]->(call:CALL)-[rc:RECEIVED_CALL]->(receiver:PERSON)'
                               ' WHERE call.id = ' + '"' + id + '"' +
                               ' RETURN call, caller, receiver')))
    return Response(dumps({"call": [serialize_call(record['call']) for record in result],
                           "caller": [serialize_person(record['caller']) for record in result],
                           "receiver": [serialize_person(record['receiver']) for record in result]
                           }),
                    mimetype="application/json")


@app.route("/network/<number>")
def get_network(number):
    db = get_db()
    results = db.read_transaction(
        lambda tx: list(tx.run('MATCH (person:PERSON)-[:KNOWS]->(knownPerson:PERSON)'
                               ' WHERE person.number = ' + '"' + number + '"' +
                               ' RETURN knownPerson')))
    return Response(dumps([serialize_person(record['knownPerson']) for record in results]),
                    mimetype="application/json")


@app.route("/network/known/<number>")
def get_network_known(number):
    db = get_db()
    results = db.read_transaction(
        lambda tx: list(tx.run('MATCH (person:PERSON)<-[:KNOWS]-(knownPerson:PERSON)'
                               ' WHERE person.number = ' + '"' + number + '"' +
                               ' RETURN knownPerson')))
    return Response(dumps([serialize_person(record['knownPerson']) for record in results]),
                    mimetype="application/json")


if __name__ == '__main__':
    logging.info('Running on port %d, database is at %s', port, url)
    app.run(port=port)

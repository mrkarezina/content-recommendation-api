from flask import Flask, request
from flask_cors import CORS
import json, requests

from article_processor import article_processor
from article_curation import get_article_dicts_from_rss
from graph_fulfilment import GraphFulfilment
from relations_query import RelationsQuery

from config import NUMBER_OF_RELATED_ARTICLES

app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": "*"}})
app.config['CORS_HEADERS'] = 'Content-Type'

"""
Server for Core API:
-Requires the user_id to identify the proper graph to query
-cluster_id is always 1

-Analyzes document
-/summary only for summary
-/summary-related for both summary and most related documents
-/explore Performs Cypher queries to explain relations
"""


def get_db_ids(user_id):
    return {
        'cluster_id': 1,
        'user_id': user_id
    }


def process_article_url(article_url, processor_id):
    article_dict, is_valid = article_processor(article_url, processor_id)

    response_articles = {
        'initial': [{
            'title': article_dict['title'],
            'date': article_dict['date'],
            'url': article_dict['url'],
            'summary': article_dict['summary'],
        }],
        'related': []
    }

    return response_articles, article_dict, is_valid


@app.route('/summary-related', methods=['POST'])
def get_related_articles():
    """
    Route takes the url of an article
    1. Downloads article
    2. Finds most similar articles by embedding and summary
    :return:
    """

    data = request.data
    data_dict = json.loads(data)

    try:
        article_url = data_dict["article_url"]
        processor_id = data_dict["processor_id"]

        response_articles, article_dict, is_valid = process_article_url(article_url, processor_id)

        db_ids = get_db_ids(data_dict["user_id"])
        graph = GraphFulfilment(db_ids)

    except Exception:
        response = app.response_class(
            response='Error processing Article',
            status=500,
        )
        return response

    most_related = graph.get_most_related_by_embedding(article_dict['embedding'])

    most_related = most_related[:NUMBER_OF_RELATED_ARTICLES]

    try:
        # Prevent the same article from being recommended
        most_related.remove(article_dict["title"])
    except ValueError:
        pass

    for related in most_related:
        response_articles['related'].append(graph.get_article_data(related))

    response = app.response_class(
        response=json.dumps(response_articles),
        status=200,
        mimetype='application/json'
    )

    return response


@app.route('/summary', methods=['POST'])
def get_article_summary():
    """
    Route takes the url of an article
    1. Downloads article
    2. Returns a summary
    :return:
    """

    data = request.data
    data_dict = json.loads(data)

    try:
        article_url = data_dict["article_url"]
        processor_id = data_dict["processor_id"]

        response_articles, article_dict, is_valid = process_article_url(article_url, processor_id)

    except Exception:
        response = app.response_class(
            response='Error processing Article',
            status=500,
        )
        return response

    response = app.response_class(
        response=json.dumps(response_articles),
        status=200,
        mimetype='application/json'
    )

    return response


@app.route('/explore', methods=['POST'])
def explore_relations():
    """
    Takes a target url in the graph
    -find the most similar to that title
    -explains connections from target to related
    :return:
    -data on inital title
    -data and explanation for most related titles
    """

    data = request.data
    data_dict = json.loads(data)

    try:
        url = data_dict["article_url"]

        db_ids = get_db_ids(data_dict["user_id"])
        graph = GraphFulfilment(db_ids)
        relations = RelationsQuery(db_ids)

    except (KeyError):
        response = app.response_class(
            response='Proper parameter missing',
            status=500,
        )
        return response

    title = graph.get_title_from_url(url)

    article_dict = graph.get_article_data(title)

    articles_data = {
        'initial': [{
            'title': article_dict['title'],
            'date': article_dict['date'],
            'url': article_dict['url'],
            'summary': article_dict['summary'],
        }],
        'related': []
    }

    most_related = graph.get_most_related_articles(title)
    most_related = most_related[:NUMBER_OF_RELATED_ARTICLES]

    for related in most_related:
        data = graph.get_article_data(related)
        data.update(relations.explain_relation(title, related))
        articles_data['related'].append(data)

    # print(json.dumps(related_articles, indent=2))
    response = app.response_class(
        response=json.dumps(articles_data),
        status=200,
        mimetype='application/json'
    )

    return response


@app.route('/rss-content', methods=['POST'])
def article_from_rss():
    """
    Takes rss link and returns article_dict
    :return:
    """

    data = request.data
    data_dict = json.loads(data)

    try:
        rss_url = data_dict["rss_url"]

    except (KeyError):
        response = app.response_class(
            response='Proper parameter missing',
            status=500,
        )
        return response

    article_dicts = get_article_dicts_from_rss(rss_url)

    # print(json.dumps(article_dicts, indent=2))
    response = app.response_class(
        response=json.dumps(article_dicts),
        status=200,
        mimetype='application/json'
    )

    return response



if __name__ == '__main__':
    # get_related_articles({
    #     'article_url': 'https://techcrunch.com/2019/02/18/apple-could-be-looking-for-its-next-big-revenue-model/'
    # })

    app.run(port=5000, debug=False)

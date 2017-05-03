from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from flask_cors import CORS

from jsonschema import validate

from geopy import Point
from geopy.distance import vincenty

import cloudinary
import cloudinary.uploader
import cloudinary.api

from datetime import datetime
from os import environ

import random

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = environ.get('OTBP_DATABASE_URI')
app.config['DEFAULT_PAGINATION_PAGE_LENGTH'] = 10
app.config['POST_SCHEMA'] = {
    "schema": "http://json-schema.org/draft-04/schema#",
    "title": "Post",
    "description": "Input data for a new post",
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "pictureId": {"type": ["integer", "null"]},
        "location": {
            "type": "object",
            "properties": {
                "lat": {"type": "number"},
                "lng": {"type": "number"}
            },
            "required": ["lat", "lng"]
        }
    },
    "required": ["text", "location"]
}
app.config['TARGET_MIN_DISTANCE'] = 100
app.config['TARGET_MAX_DISTANCE'] = 200

CORS(app)
db = SQLAlchemy(app)

cloudinary.config(
    cloud_name=environ.get('OTBP_CLOUDINARY_CLOUD_NAME'),
    api_key=environ.get('OTBP_CLOUDINARY_API_KEY'),
    api_secret=environ.get('OTBP_CLOUDINARY_API_SECRET')
)


class TargetLocation(db.Model):
    key = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)

    def toSimpleDict(self):
        return {
            'key': self.key,
            'position': {
                'lat': self.lat,
                'lng': self.lng,
            },
            'totalVisitors': 10,
            'averageVisitorsPerHour': 10
        }


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           nullable=False)
    text = db.Column(db.String(140), nullable=False)
    final_distance = db.Column(db.Float, nullable=False)

    location_id = db.Column(db.Integer,
                            db.ForeignKey('target_location.key'),
                            nullable=False)
    location = db.relationship('TargetLocation',
                               backref=db.backref('posts', lazy=True))

    image_id = db.Column(db.Integer,
                         db.ForeignKey('saved_image.id'),
                         nullable=True)
    image = db.relationship('SavedImage')

    def toSimpleDict(self):
        return {
            'timestamp': self.created_at.timestamp(),
            'pictureUrl': getattr(self.image, 'url', None),
            'finalDistance': self.final_distance,
            'text': self.text
        }


class SavedImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           nullable=False)
    url = db.Column(db.String(512), nullable=True)


class EasyPagination(object):
    def __init__(self, data, pageNumber, lastPage):
        self.data = data
        self.pageNumber = pageNumber
        self.lastPage = lastPage

    def toSimpleDict(self):
        return {
            'data': self.data,
            'pageNumber': self.pageNumber,
            'lastPage': self.lastPage
        }


def _haversine(a, b):
    return vincenty((a.lat, a.lng), (b.lat, b.lng)).meters


@app.route('/')
def index():
    return 'todo: find an api details generator like swagger?'


@app.route('/target/<location>', methods=['get'])
def get_target_by_location(location):
    # location should be in format `lat,lng`
    source_lat, source_lng = list(map(lambda x: float(x), location.split(',')))
    source_location = TargetLocation(lat=source_lat, lng=source_lng)

    # attempt to find an existing location
    target_list = TargetLocation.query \
        .filter(
            # check for results created today
            func.date(TargetLocation.created_at) == func.current_date()
        ) \
        .all()

    sorted_target_list = sorted(target_list,
                                key=lambda t: _haversine(source_location, t))
    if len(sorted_target_list) > 0:
        target = sorted_target_list[0]

        haversine_distance = _haversine(
            target,
            source_location)

        if haversine_distance < app.config['TARGET_MAX_DISTANCE']:
            return jsonify(target.toSimpleDict())

    # naively create a target between MIN to MAX m away from current location
    angle = random.randint(1, 360)
    pdistance = random.randint(app.config['TARGET_MIN_DISTANCE'],
                               app.config['TARGET_MAX_DISTANCE'])
    pdistance /= 1000

    target_lat, target_lng, alt = vincenty(kilometers=pdistance) \
        .destination(Point(source_lat, source_lng), angle)

    target_location = TargetLocation(lat=target_lat,
                                     lng=target_lng)

    db.session.add(target_location)
    db.session.commit()

    return jsonify(target_location.toSimpleDict())


@app.route('/target/key/<int:key>', methods=['get'])
def get_target_by_key(key):
    target = TargetLocation.query.get_or_404(key)
    return jsonify(target.toSimpleDict())


@app.route('/posts/<int:key>/<int:page>', methods=['get'])
def get_posts_by_page(key, page=1):
    pagination = Post.query \
                     .filter(Post.location_id == key) \
                     .paginate(page,
                               app.config['DEFAULT_PAGINATION_PAGE_LENGTH'],
                               False)

    posts = list(map(lambda x: x.toSimpleDict(), pagination.items))

    easy_pagination = EasyPagination(posts, page, not pagination.has_next)

    return jsonify(easy_pagination.toSimpleDict())


@app.route('/posts/<int:key>', methods=['post'])
def create_post(key):
    data = request.get_json()
    validate(data, app.config['POST_SCHEMA'])
    target_location = TargetLocation.query.get_or_404(key)
    post = Post(text=data['text'],
                image_id=data.get('pictureId', None),
                final_distance=_haversine(
                    TargetLocation(
                        lat=data['location']['lat'],
                        lng=data['location']['lng']
                    ),
                    target_location),
                location_id=key)
    db.session.add(post)
    db.session.commit()
    return jsonify({'success': True}), 201


@app.route('/image', methods=['post'])
def upload_photo():
    cloudinary_data = cloudinary.uploader.upload(request.files['image'])
    image = SavedImage(url=cloudinary_data['secure_url'])
    db.session.add(image)
    db.session.commit()

    return jsonify({
        'pictureId': image.id
    })


if __name__ == '__main__':
    app.run(debug=environ.get('OTBP_DEBUG_MODE', False))

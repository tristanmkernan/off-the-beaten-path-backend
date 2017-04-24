from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from jsonschema import validate
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = \
                        'mysql+pymysql://root:python@localhost/otbp'
app.config['DEFAULT_PAGINATION_PAGE_LENGTH'] = 10
app.config['POST_SCHEMA'] = {
    "schema": "http://json-schema.org/draft-04/schema#",
    "title": "Post",
    "description": "Input data for a new post",
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "pictureId": {"type": "integer", "minimum": 0},
        "finalDistance": {"type": "number"}
    },
    "required": ["text", "finalDistance"]
}

db = SQLAlchemy(app)


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
            'lat': self.lat,
            'lng': self.lng
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
    image = db.relationship('SavedImage')  # some kind of relationship here

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


@app.route('/')
def index():
    return 'todo: find an api details generator like swagger?'


@app.route('/target/<location>', methods=['get'])
def get_target_by_location(location):
    return '', 200


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
    post = Post(text=data['text'],
                image_id=data.get('pictureId', None),
                final_distance=data['finalDistance'],
                location_id=key)
    db.session.add(post)
    db.session.commit()
    return 'Successfully created post!', 201


if __name__ == '__main__':
    app.run(debug=True)

import os
import app as my_app
import unittest
import tempfile
import json


class AppTestCase(unittest.TestCase):

    def setUp(self):
        my_app.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        my_app.app.config['TESTING'] = True
        self.app = my_app.app.test_client()
        with my_app.app.app_context():
            my_app.db.create_all()

    def tearDown(self):
        with my_app.app.app_context():
            my_app.db.drop_all()

    def test_index(self):
        rv = self.app.get('/')
        self.assertIn(b'todo: find an api details generator like swagger?', rv.data)

    def test_get_target_by_key_404(self):
        # targets should be empty
        with my_app.app.app_context():
            self.assertEqual(my_app.TargetLocation.query.count(), 0)

        # target endpoint should return 404 when the item is missing
        rv = self.app.get('/target/key/0')
        self.assertEqual(rv.status_code, 404)

    def test_get_existing_target_by_key(self):
        # add a new target to the database
        with my_app.app.app_context():
            target = my_app.TargetLocation(lat=1, lng=1)
            my_app.db.session.add(target)
            my_app.db.session.commit()
            target_id = getattr(target, 'key', None)

        # retrieve target from api
        self.assertIsNotNone(target_id)

        rv = self.app.get(f'/target/key/{target.key}')
        rv_json = json.loads(rv.get_data())
        self.assertDictContainsSubset({'position': {'lat': 1, 'lng': 1}}, rv_json)

    def test_create_post(self):
        # create a target, then create a post
        with my_app.app.app_context():
            self.assertEqual(my_app.TargetLocation.query.count(), 0)
            self.assertEqual(my_app.Post.query.count(), 0)
            
            target = my_app.TargetLocation(lat=1, lng=1)
            my_app.db.session.add(target)
            my_app.db.session.commit()

            post = my_app.Post(text='test',
                               image_id=None,
                               final_distance=1,
                               location_id=target.key)

            my_app.db.session.add(post)
            my_app.db.session.commit()

            self.assertEqual(my_app.TargetLocation.query.count(), 1)
            self.assertEqual(my_app.Post.query.count(), 1)

            post_from_db = my_app.Post.query.first()
            self.assertDictEqual(post.toSimpleDict(),
                                 post_from_db.toSimpleDict())

    def test_get_post_by_page(self):
        # create a target, then create a post
        with my_app.app.app_context():
            self.assertEqual(my_app.TargetLocation.query.count(), 0)
            self.assertEqual(my_app.Post.query.count(), 0)
            
            target = my_app.TargetLocation(lat=1, lng=1)
            my_app.db.session.add(target)
            my_app.db.session.commit()

            posts = []
            for i in range(0, 100):
                post = my_app.Post(text='test',
                                   image_id=None,
                                   final_distance=1,
                                   location_id=target.key)
                my_app.db.session.add(post)
                my_app.db.session.commit()
                posts.append(post.toSimpleDict())
            
            self.assertEqual(my_app.TargetLocation.query.count(), 1)
            self.assertEqual(my_app.Post.query.count(), 100)

            rv = self.app.get(f'/posts/{target.key}/1')
            rv_json = json.loads(rv.get_data())

            easy_pagination = my_app.EasyPagination(posts[0:10], 1, False)
            self.assertDictEqual(easy_pagination.toSimpleDict(), rv_json)

    def test_get_target_by_location(self):
        # create a target, then create a post
        with my_app.app.app_context():
            self.assertEqual(my_app.TargetLocation.query.count(), 0)

            self.fail("finish the test by moving sql math to python")
            
            rv = self.app.get('/target/1,1')

            self.assertEqual(my_app.TargetLocation.query.count(), 1)

            

if __name__ == '__main__':
    unittest.main()

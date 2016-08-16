# -*- coding: utf-8 -*-

import time
import os

from sys import argv
from uuid import uuid4
# from pymysql import connect

from torndb import Connection

from logging import debug, info, warning, error, exception

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.web import RequestHandler, ErrorHandler, Application, authenticated, asynchronous, StaticFileHandler
from tornado.log import define_logging_options
from tornado import autoreload, gen
from tornado.options import define, options, parse_command_line, parse_config_file
from tornado.httpclient import AsyncHTTPClient

import feedparser
from time import mktime
from datetime import datetime, timedelta

from urllib2 import quote, unquote


def beuDate(rawTime):
    return datetime.fromtimestamp(mktime(rawTime))

def feed_update(db = None):
    http_client = AsyncHTTPClient()
    urls = [
        'http://www.artlebedev.ru/kovodstvo/sections/kovodstvo.rdf',
        'https://meduza.io/rss/all',
        'https://vc.ru/feed']

    for i in urls:
        debug('start: %s' % i)

        def feed_rerurn(url):
            def fundc(response):
                debug(url)
                debug(response)
            return fundc

        http_client.fetch(i, feed_rerurn(i))


class CommonHandler(RequestHandler):
    def get_current_user(self):
        # placeholder: Пользователь всегда в системе.
        return 31337

    @property
    def db(self):
        if not hasattr(self, '_db') or not self._db:
            # class torndb.Connection(host, database, user=None, password=None,
            # max_idle_time=25200, connect_timeout=0, time_zone='+0:00',
            # charset='utf8', sql_mode='TRADITIONAL', **kwargs)
            self._db = Connection('127.0.0.1', 'zenreader', user='root', password='password')

        return self._db


class FastFeed(RequestHandler):

    def get(self):
        u = 'http://artgorbunov.ru/news/rss/'  # or u = rawdata
        u = self.get_argument('url', None)

        if not u:
            self.redirect('/')
            return

        r = feedparser.parse(u)

        self.render('live.html', feed=r, beuDate=beuDate)

        return
        # print r.feed.title
        # i = 0;
        # for item in r.entries:
        #     i+=1
        #     print '\n-=-=-=- %s -=-=-=-' % i
        #     print item.title
        #     # print item.updated # Unicode String
        #     dt = datetime.fromtimestamp(mktime(item.published_parsed))
        #
        #     print dt.strftime('%Y %m %d') # Unicode String
        #     print item.link


class Home(CommonHandler):

    def get(self):
        # debug(self.db.query('SELECT now()'))
        self.render('main.html')


# http://torndb.readthedocs.org/en/latest/

# db = torndb.Connection("localhost", "mydatabase")
# for article in db.query("SELECT * FROM articles"):
#     print article.title

class ManageFeeds(CommonHandler):

    @authenticated
    def get(self):
        sql = 'SELECT * FROM feeds WHERE user_id = %s'

        feeds = self.db.query(sql, self.current_user)
        # debug(feeds)
        # debug(type(feeds))
        self.render('settings.html', feeds=feeds, quote=quote)

    @authenticated
    def post(self):
        action = self.get_argument('action', None)
        debug(action)
        if action != 'add' and action != 'delete':
            self.redirect('/settings/')
            return

        if action == 'add':
            # проверить, что url == rss
            # добавить в БД
            url = self.get_argument('url', None)
            feed = feedparser.parse(url)
            title = feed.feed.title

            check_sql = 'SELECT id from feeds where user_id = %s and url = %s limit 1;'
            duplicates = self.db.query(check_sql, self.current_user, url)

            if duplicates:
                self.redirect('/settings/')
                return

            sql = 'INSERT INTO feeds (user_id, url, title) VALUES (%s, %s, %s)'
            self.db.execute(sql, self.current_user, url, title)
        elif action == 'delete':
            # проверить существование и удалить (просто удалить)
            id = self.get_argument('id', None)
            sql = 'DELETE from feeds WHERE user_id = %s and id = %s'
            self.db.execute(sql, self.current_user, id)
        self.redirect('/settings/')
        return


if __name__ == "__main__":
    CURRENT_PATH = os.path.dirname(os.path.abspath(__file__))
    TEMPLATE_PATH = os.path.join(CURRENT_PATH, 'templates')
    STATIC_PATH = os.path.join(CURRENT_PATH, 'static')
    
    define("debug", type=bool, default=False)
    define("templates_path", default=TEMPLATE_PATH)
    define("static_path", default=STATIC_PATH)
    
    define('port', type=int, default=11008)
    
    define("db_username", type=str, default="123")
    define("db_pass", type=str, default="123")
    
    if len(argv) > 1 and os.path.exists(argv[1]):
        parse_config_file(argv[1])
    else:
        warning('Running without config: terminate')
        print('Example usage:')
        print('  python webapp.py /path/to/production.conf [params]')
        exit()
    
    urls = [
        ('/', Home),
        (r'/live/', FastFeed),
        (r'/settings/', ManageFeeds),
        (r'/static/(.*)', StaticFileHandler, dict(path=options.static_path))
    ]
    
    settings = dict(
        debug=options.debug,
        template_path=options.templates_path,
        static_path=options.static_path,
        autoescape=None,
        cookie_secret='nklfsdkbfhbkewbkbjkwebjkv',
        # db = DBInstance(options.db_username, options.db_pass),
        options=options
    )
    
    class ZenApp(Application):
        def zenupdete(self):
            db = self.settings['options'].port
            
            # Запустить обновление фидов
            feed_update()
            # debug(db)
            # debug('zenupdete')
            debug(datetime.utcnow())
            
    app = ZenApp(urls, **settings)
    
    http_server = HTTPServer(app, xheaders=True)
    http_server.listen(options.port)
    
    debug('started http://localhost:%s/' % options.port)
    
    autoreload.start()
    loop = IOLoop.instance()
    
    MINUTE = 1000 * 60
    
    PeriodicCallback(app.zenupdete, MINUTE / 6, loop).start()
    loop.start()

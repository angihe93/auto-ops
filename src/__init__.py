from flask import Flask

# from somewhere import login_manager

def create_app(config_object):
    app = Flask(__name__)

    app.config.from_object(config_object)

    # login_manager.init_app(app)
    from .routes import auth, main, calendar
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(calendar)

    return app

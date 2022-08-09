from src import create_app
from src.utils import FlaskConfig

flask_config = FlaskConfig()
app = create_app(config_object=flask_config)

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8080,
        debug=True,
        ssl_context='adhoc'
    )

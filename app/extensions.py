from flask_appbuilder import AppBuilder
from flask_appbuilder.utils.legacy import get_sqla_class
from flask_migrate import Migrate

db = get_sqla_class()()
appbuilder = AppBuilder()
migrate = Migrate()

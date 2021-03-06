import os
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from votr import votr, db

# votr.config.from_object(os.environ['APP_SETTINGS'])

migrate = Migrate(votr, db)
manager = Manager(votr)

manager.add_command('db', MigrateCommand)


if __name__ == '__main__':
    manager.run()
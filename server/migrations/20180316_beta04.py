from mongodb_migrations.base import BaseMigration

class Migration (BaseMigration):

    def upgrade(self):
        for config in self.db.configuration_group.find():
            if 'user' in config and config['user']:
                user = self.db.user.find_one({'_id' : config['user']})
                config['code'] = user['email'] + '_' + config['name']
            else:
                config['code'] = config['name']
            self.db.configuration_group.save(config)

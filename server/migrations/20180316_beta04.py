from mongodb_migrations.base import BaseMigration

class Migration (BaseMigration):

    def upgrade(self):
        i = 1
        for config in self.db.configuration_group.find():
            i += 1
            if 'user' in config and config['user']:
                user = self.db.user.find_one({'_id' : config['user']})
                config['code'] = str(i)
            else:
                config['code'] = config['name']
            self.db.configuration_group.save(config)

import logging

from mongodb_migrations.base import BaseMigration

class Migration (BaseMigration):

    def upgrade(self):
        # as soon as we change 'code' to sparse, index need to be recreated
        self.db.configuration_group.drop_indexes()

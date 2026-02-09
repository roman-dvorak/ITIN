class DhcpDatabaseRouter:
    """
    Router pro DHCP databázi (Kea).
    Směruje modely z models_dhcp.py na dhcp_database.
    """
    
    dhcp_db = 'dhcp_database'
    
    def _is_dhcp_model(self, model):
        return model._meta.app_label == 'inventory' and 'models_dhcp' in str(model.__module__)
    
    def db_for_read(self, model, **hints):
        if self._is_dhcp_model(model):
            return self.dhcp_db
        return None
    
    def db_for_write(self, model, **hints):
        if self._is_dhcp_model(model):
            return self.dhcp_db
        return None
    
    def allow_relation(self, obj1, obj2, **hints):
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == self.dhcp_db:
            return False
        return None

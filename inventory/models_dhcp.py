# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class DdnsReplaceClientNameTypes(models.Model):
    type = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'ddns_replace_client_name_types'


class Dhcp4Audit(models.Model):
    id = models.AutoField(primary_key=True)
    object_type = models.CharField(max_length=256)
    object_id = models.BigIntegerField()
    modification_type = models.ForeignKey('Modification', models.DO_NOTHING, db_column='modification_type')
    revision = models.ForeignKey('Dhcp4AuditRevision', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'dhcp4_audit'


class Dhcp4AuditRevision(models.Model):
    modification_ts = models.DateTimeField()
    log_message = models.TextField(blank=True, null=True)
    server_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp4_audit_revision'


class Dhcp4ClientClass(models.Model):
    name = models.CharField(unique=True, max_length=128)
    test = models.TextField(blank=True, null=True)
    next_server = models.GenericIPAddressField(blank=True, null=True)
    server_hostname = models.CharField(max_length=128, blank=True, null=True)
    boot_file_name = models.CharField(max_length=512, blank=True, null=True)
    only_in_additional_list = models.BooleanField()
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    min_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    max_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    depend_on_known_directly = models.BooleanField()
    follow_class_name = models.CharField(max_length=128, blank=True, null=True)
    modification_ts = models.DateTimeField()
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.
    offer_lifetime = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp4_client_class'


class Dhcp4ClientClassDependency(models.Model):
    pk = models.CompositePrimaryKey('class_id', 'dependency_id')
    class_field = models.ForeignKey(Dhcp4ClientClass, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    dependency = models.ForeignKey(Dhcp4ClientClass, models.DO_NOTHING, related_name='dhcp4clientclassdependency_dependency_set')

    class Meta:
        managed = False
        db_table = 'dhcp4_client_class_dependency'


class Dhcp4ClientClassOrder(models.Model):
    class_field = models.OneToOneField(Dhcp4ClientClass, models.DO_NOTHING, db_column='class_id', primary_key=True)  # Field renamed because it was a Python reserved word.
    order_index = models.BigIntegerField()
    depend_on_known_indirectly = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'dhcp4_client_class_order'


class Dhcp4ClientClassServer(models.Model):
    pk = models.CompositePrimaryKey('class_id', 'server_id')
    class_field = models.ForeignKey(Dhcp4ClientClass, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    server = models.ForeignKey('Dhcp4Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp4_client_class_server'


class Dhcp4GlobalParameter(models.Model):
    name = models.CharField(max_length=128)
    value = models.TextField()
    modification_ts = models.DateTimeField()
    parameter_type = models.ForeignKey('ParameterDataType', models.DO_NOTHING, db_column='parameter_type')

    class Meta:
        managed = False
        db_table = 'dhcp4_global_parameter'


class Dhcp4GlobalParameterServer(models.Model):
    pk = models.CompositePrimaryKey('parameter_id', 'server_id')
    parameter = models.ForeignKey(Dhcp4GlobalParameter, models.DO_NOTHING)
    server = models.ForeignKey('Dhcp4Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp4_global_parameter_server'


class Dhcp4OptionDef(models.Model):
    code = models.SmallIntegerField()
    name = models.CharField(max_length=128)
    space = models.CharField(max_length=128)
    type = models.ForeignKey('OptionDefDataType', models.DO_NOTHING, db_column='type')
    modification_ts = models.DateTimeField()
    is_array = models.BooleanField()
    encapsulate = models.CharField(max_length=128)
    record_types = models.CharField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.
    class_field = models.ForeignKey(Dhcp4ClientClass, models.DO_NOTHING, db_column='class_id', blank=True, null=True)  # Field renamed because it was a Python reserved word.

    class Meta:
        managed = False
        db_table = 'dhcp4_option_def'


class Dhcp4OptionDefServer(models.Model):
    pk = models.CompositePrimaryKey('option_def_id', 'server_id')
    option_def = models.ForeignKey(Dhcp4OptionDef, models.DO_NOTHING)
    server = models.ForeignKey('Dhcp4Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp4_option_def_server'


class Dhcp4Options(models.Model):
    option_id = models.AutoField(primary_key=True)
    code = models.SmallIntegerField()
    value = models.BinaryField(blank=True, null=True)
    formatted_value = models.TextField(blank=True, null=True)
    space = models.CharField(max_length=128, blank=True, null=True)
    persistent = models.BooleanField()
    dhcp_client_class = models.CharField(max_length=128, blank=True, null=True)
    dhcp4_subnet = models.ForeignKey('Dhcp4Subnet', models.DO_NOTHING, blank=True, null=True)
    host = models.ForeignKey('Hosts', models.DO_NOTHING, blank=True, null=True)
    scope = models.ForeignKey('DhcpOptionScope', models.DO_NOTHING)
    user_context = models.TextField(blank=True, null=True)
    shared_network_name = models.ForeignKey('Dhcp4SharedNetwork', models.DO_NOTHING, db_column='shared_network_name', to_field='name', blank=True, null=True)
    pool = models.ForeignKey('Dhcp4Pool', models.DO_NOTHING, blank=True, null=True)
    modification_ts = models.DateTimeField()
    cancelled = models.BooleanField()
    client_classes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp4_options'


class Dhcp4OptionsServer(models.Model):
    pk = models.CompositePrimaryKey('option_id', 'server_id')
    option = models.ForeignKey(Dhcp4Options, models.DO_NOTHING)
    server = models.ForeignKey('Dhcp4Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp4_options_server'


class Dhcp4Pool(models.Model):
    start_address = models.GenericIPAddressField()
    end_address = models.GenericIPAddressField()
    subnet = models.ForeignKey('Dhcp4Subnet', models.DO_NOTHING)
    modification_ts = models.DateTimeField()
    client_classes = models.TextField(blank=True, null=True)
    evaluate_additional_classes = models.TextField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'dhcp4_pool'


class Dhcp4Server(models.Model):
    tag = models.CharField(unique=True, max_length=64)
    description = models.TextField(blank=True, null=True)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp4_server'


class Dhcp4SharedNetwork(models.Model):
    name = models.CharField(unique=True, max_length=128)
    client_classes = models.TextField(blank=True, null=True)
    interface = models.CharField(max_length=128, blank=True, null=True)
    match_client_id = models.BooleanField(blank=True, null=True)
    modification_ts = models.DateTimeField()
    rebind_timer = models.BigIntegerField(blank=True, null=True)
    relay = models.TextField(blank=True, null=True)
    renew_timer = models.BigIntegerField(blank=True, null=True)
    evaluate_additional_classes = models.TextField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    authoritative = models.BooleanField(blank=True, null=True)
    calculate_tee_times = models.BooleanField(blank=True, null=True)
    t1_percent = models.FloatField(blank=True, null=True)
    t2_percent = models.FloatField(blank=True, null=True)
    boot_file_name = models.CharField(max_length=128, blank=True, null=True)
    next_server = models.GenericIPAddressField(blank=True, null=True)
    server_hostname = models.CharField(max_length=64, blank=True, null=True)
    min_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    max_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    ddns_send_updates = models.BooleanField(blank=True, null=True)
    ddns_override_no_update = models.BooleanField(blank=True, null=True)
    ddns_override_client_update = models.BooleanField(blank=True, null=True)
    ddns_replace_client_name = models.ForeignKey(DdnsReplaceClientNameTypes, models.DO_NOTHING, db_column='ddns_replace_client_name', blank=True, null=True)
    ddns_generated_prefix = models.CharField(max_length=255, blank=True, null=True)
    ddns_qualifying_suffix = models.CharField(max_length=255, blank=True, null=True)
    reservations_global = models.BooleanField(blank=True, null=True)
    reservations_in_subnet = models.BooleanField(blank=True, null=True)
    reservations_out_of_pool = models.BooleanField(blank=True, null=True)
    cache_threshold = models.FloatField(blank=True, null=True)
    cache_max_age = models.BigIntegerField(blank=True, null=True)
    offer_lifetime = models.BigIntegerField(blank=True, null=True)
    allocator = models.TextField(blank=True, null=True)
    ddns_ttl_percent = models.FloatField(blank=True, null=True)
    ddns_ttl = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_min = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_max = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp4_shared_network'


class Dhcp4SharedNetworkServer(models.Model):
    pk = models.CompositePrimaryKey('shared_network_id', 'server_id')
    shared_network = models.ForeignKey(Dhcp4SharedNetwork, models.DO_NOTHING)
    server = models.ForeignKey(Dhcp4Server, models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp4_shared_network_server'


class Dhcp4Subnet(models.Model):
    subnet_id = models.BigIntegerField(primary_key=True)
    subnet_prefix = models.CharField(unique=True, max_length=64)
    interface_4o6 = models.CharField(max_length=128, blank=True, null=True)
    interface_id_4o6 = models.CharField(max_length=128, blank=True, null=True)
    subnet_4o6 = models.CharField(max_length=64, blank=True, null=True)
    boot_file_name = models.CharField(max_length=128, blank=True, null=True)
    client_classes = models.TextField(blank=True, null=True)
    interface = models.CharField(max_length=128, blank=True, null=True)
    match_client_id = models.BooleanField(blank=True, null=True)
    modification_ts = models.DateTimeField()
    next_server = models.GenericIPAddressField(blank=True, null=True)
    rebind_timer = models.BigIntegerField(blank=True, null=True)
    relay = models.TextField(blank=True, null=True)
    renew_timer = models.BigIntegerField(blank=True, null=True)
    evaluate_additional_classes = models.TextField(blank=True, null=True)
    server_hostname = models.CharField(max_length=64, blank=True, null=True)
    shared_network_name = models.ForeignKey(Dhcp4SharedNetwork, models.DO_NOTHING, db_column='shared_network_name', to_field='name', blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    authoritative = models.BooleanField(blank=True, null=True)
    calculate_tee_times = models.BooleanField(blank=True, null=True)
    t1_percent = models.FloatField(blank=True, null=True)
    t2_percent = models.FloatField(blank=True, null=True)
    min_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    max_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    ddns_send_updates = models.BooleanField(blank=True, null=True)
    ddns_override_no_update = models.BooleanField(blank=True, null=True)
    ddns_override_client_update = models.BooleanField(blank=True, null=True)
    ddns_replace_client_name = models.ForeignKey(DdnsReplaceClientNameTypes, models.DO_NOTHING, db_column='ddns_replace_client_name', blank=True, null=True)
    ddns_generated_prefix = models.CharField(max_length=255, blank=True, null=True)
    ddns_qualifying_suffix = models.CharField(max_length=255, blank=True, null=True)
    reservations_global = models.BooleanField(blank=True, null=True)
    reservations_in_subnet = models.BooleanField(blank=True, null=True)
    reservations_out_of_pool = models.BooleanField(blank=True, null=True)
    cache_threshold = models.FloatField(blank=True, null=True)
    cache_max_age = models.BigIntegerField(blank=True, null=True)
    offer_lifetime = models.BigIntegerField(blank=True, null=True)
    allocator = models.TextField(blank=True, null=True)
    ddns_ttl_percent = models.FloatField(blank=True, null=True)
    ddns_ttl = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_min = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_max = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp4_subnet'


class Dhcp4SubnetServer(models.Model):
    pk = models.CompositePrimaryKey('subnet_id', 'server_id')
    subnet = models.ForeignKey(Dhcp4Subnet, models.DO_NOTHING)
    server = models.ForeignKey(Dhcp4Server, models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp4_subnet_server'


class Dhcp6Audit(models.Model):
    id = models.AutoField(primary_key=True)
    object_type = models.CharField(max_length=256)
    object_id = models.BigIntegerField()
    modification_type = models.ForeignKey('Modification', models.DO_NOTHING, db_column='modification_type')
    revision = models.ForeignKey('Dhcp6AuditRevision', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'dhcp6_audit'


class Dhcp6AuditRevision(models.Model):
    modification_ts = models.DateTimeField()
    log_message = models.TextField(blank=True, null=True)
    server_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp6_audit_revision'


class Dhcp6ClientClass(models.Model):
    name = models.CharField(unique=True, max_length=128)
    test = models.TextField(blank=True, null=True)
    only_in_additional_list = models.BooleanField()
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    min_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    max_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    depend_on_known_directly = models.BooleanField()
    follow_class_name = models.CharField(max_length=128, blank=True, null=True)
    modification_ts = models.DateTimeField()
    preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    min_preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    max_preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'dhcp6_client_class'


class Dhcp6ClientClassDependency(models.Model):
    pk = models.CompositePrimaryKey('class_id', 'dependency_id')
    class_field = models.ForeignKey(Dhcp6ClientClass, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    dependency = models.ForeignKey(Dhcp6ClientClass, models.DO_NOTHING, related_name='dhcp6clientclassdependency_dependency_set')

    class Meta:
        managed = False
        db_table = 'dhcp6_client_class_dependency'


class Dhcp6ClientClassOrder(models.Model):
    class_field = models.OneToOneField(Dhcp6ClientClass, models.DO_NOTHING, db_column='class_id', primary_key=True)  # Field renamed because it was a Python reserved word.
    order_index = models.BigIntegerField()
    depend_on_known_indirectly = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'dhcp6_client_class_order'


class Dhcp6ClientClassServer(models.Model):
    pk = models.CompositePrimaryKey('class_id', 'server_id')
    class_field = models.ForeignKey(Dhcp6ClientClass, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    server = models.ForeignKey('Dhcp6Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp6_client_class_server'


class Dhcp6GlobalParameter(models.Model):
    name = models.CharField(max_length=128)
    value = models.TextField()
    modification_ts = models.DateTimeField()
    parameter_type = models.ForeignKey('ParameterDataType', models.DO_NOTHING, db_column='parameter_type')

    class Meta:
        managed = False
        db_table = 'dhcp6_global_parameter'


class Dhcp6GlobalParameterServer(models.Model):
    pk = models.CompositePrimaryKey('parameter_id', 'server_id')
    parameter = models.ForeignKey(Dhcp6GlobalParameter, models.DO_NOTHING)
    server = models.ForeignKey('Dhcp6Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp6_global_parameter_server'


class Dhcp6OptionDef(models.Model):
    code = models.SmallIntegerField()
    name = models.CharField(max_length=128)
    space = models.CharField(max_length=128)
    type = models.ForeignKey('OptionDefDataType', models.DO_NOTHING, db_column='type')
    modification_ts = models.DateTimeField()
    is_array = models.BooleanField()
    encapsulate = models.CharField(max_length=128)
    record_types = models.CharField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.
    class_field = models.ForeignKey(Dhcp6ClientClass, models.DO_NOTHING, db_column='class_id', blank=True, null=True)  # Field renamed because it was a Python reserved word.

    class Meta:
        managed = False
        db_table = 'dhcp6_option_def'


class Dhcp6OptionDefServer(models.Model):
    pk = models.CompositePrimaryKey('option_def_id', 'server_id')
    option_def = models.ForeignKey(Dhcp6OptionDef, models.DO_NOTHING)
    server = models.ForeignKey('Dhcp6Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp6_option_def_server'


class Dhcp6Options(models.Model):
    option_id = models.AutoField(primary_key=True)
    code = models.IntegerField()
    value = models.BinaryField(blank=True, null=True)
    formatted_value = models.TextField(blank=True, null=True)
    space = models.CharField(max_length=128, blank=True, null=True)
    persistent = models.BooleanField()
    dhcp_client_class = models.CharField(max_length=128, blank=True, null=True)
    dhcp6_subnet = models.ForeignKey('Dhcp6Subnet', models.DO_NOTHING, blank=True, null=True)
    host = models.ForeignKey('Hosts', models.DO_NOTHING, blank=True, null=True)
    scope = models.ForeignKey('DhcpOptionScope', models.DO_NOTHING)
    user_context = models.TextField(blank=True, null=True)
    shared_network_name = models.ForeignKey('Dhcp6SharedNetwork', models.DO_NOTHING, db_column='shared_network_name', to_field='name', blank=True, null=True)
    pool = models.ForeignKey('Dhcp6Pool', models.DO_NOTHING, blank=True, null=True)
    pd_pool = models.ForeignKey('Dhcp6PdPool', models.DO_NOTHING, blank=True, null=True)
    modification_ts = models.DateTimeField()
    cancelled = models.BooleanField()
    client_classes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp6_options'


class Dhcp6OptionsServer(models.Model):
    pk = models.CompositePrimaryKey('option_id', 'server_id')
    option = models.ForeignKey(Dhcp6Options, models.DO_NOTHING)
    server = models.ForeignKey('Dhcp6Server', models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp6_options_server'


class Dhcp6PdPool(models.Model):
    prefix = models.CharField(max_length=45)
    prefix_length = models.SmallIntegerField()
    delegated_prefix_length = models.SmallIntegerField()
    subnet = models.ForeignKey('Dhcp6Subnet', models.DO_NOTHING)
    modification_ts = models.DateTimeField()
    excluded_prefix = models.CharField(max_length=45, blank=True, null=True)
    excluded_prefix_length = models.SmallIntegerField()
    client_classes = models.TextField(blank=True, null=True)
    evaluate_additional_classes = models.TextField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'dhcp6_pd_pool'


class Dhcp6Pool(models.Model):
    start_address = models.GenericIPAddressField()
    end_address = models.GenericIPAddressField()
    subnet = models.ForeignKey('Dhcp6Subnet', models.DO_NOTHING)
    modification_ts = models.DateTimeField()
    client_classes = models.TextField(blank=True, null=True)
    evaluate_additional_classes = models.TextField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'dhcp6_pool'


class Dhcp6Server(models.Model):
    tag = models.CharField(unique=True, max_length=64)
    description = models.TextField(blank=True, null=True)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp6_server'


class Dhcp6SharedNetwork(models.Model):
    name = models.CharField(unique=True, max_length=128)
    client_classes = models.TextField(blank=True, null=True)
    interface = models.CharField(max_length=128, blank=True, null=True)
    modification_ts = models.DateTimeField()
    preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    rapid_commit = models.BooleanField(blank=True, null=True)
    rebind_timer = models.BigIntegerField(blank=True, null=True)
    relay = models.TextField(blank=True, null=True)
    renew_timer = models.BigIntegerField(blank=True, null=True)
    evaluate_additional_classes = models.TextField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    calculate_tee_times = models.BooleanField(blank=True, null=True)
    t1_percent = models.FloatField(blank=True, null=True)
    t2_percent = models.FloatField(blank=True, null=True)
    interface_id = models.BinaryField(blank=True, null=True)
    min_preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    max_preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    min_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    max_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    ddns_send_updates = models.BooleanField(blank=True, null=True)
    ddns_override_no_update = models.BooleanField(blank=True, null=True)
    ddns_override_client_update = models.BooleanField(blank=True, null=True)
    ddns_replace_client_name = models.ForeignKey(DdnsReplaceClientNameTypes, models.DO_NOTHING, db_column='ddns_replace_client_name', blank=True, null=True)
    ddns_generated_prefix = models.CharField(max_length=255, blank=True, null=True)
    ddns_qualifying_suffix = models.CharField(max_length=255, blank=True, null=True)
    reservations_global = models.BooleanField(blank=True, null=True)
    reservations_in_subnet = models.BooleanField(blank=True, null=True)
    reservations_out_of_pool = models.BooleanField(blank=True, null=True)
    cache_threshold = models.FloatField(blank=True, null=True)
    cache_max_age = models.BigIntegerField(blank=True, null=True)
    allocator = models.TextField(blank=True, null=True)
    pd_allocator = models.TextField(blank=True, null=True)
    ddns_ttl_percent = models.FloatField(blank=True, null=True)
    ddns_ttl = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_min = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_max = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp6_shared_network'


class Dhcp6SharedNetworkServer(models.Model):
    pk = models.CompositePrimaryKey('shared_network_id', 'server_id')
    shared_network = models.ForeignKey(Dhcp6SharedNetwork, models.DO_NOTHING)
    server = models.ForeignKey(Dhcp6Server, models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp6_shared_network_server'


class Dhcp6Subnet(models.Model):
    subnet_id = models.BigIntegerField(primary_key=True)
    subnet_prefix = models.CharField(unique=True, max_length=64)
    client_classes = models.TextField(blank=True, null=True)
    interface = models.CharField(max_length=128, blank=True, null=True)
    modification_ts = models.DateTimeField()
    preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    rapid_commit = models.BooleanField(blank=True, null=True)
    rebind_timer = models.BigIntegerField(blank=True, null=True)
    relay = models.TextField(blank=True, null=True)
    renew_timer = models.BigIntegerField(blank=True, null=True)
    evaluate_additional_classes = models.TextField(blank=True, null=True)
    shared_network_name = models.ForeignKey(Dhcp6SharedNetwork, models.DO_NOTHING, db_column='shared_network_name', to_field='name', blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)  # This field type is a guess.
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    calculate_tee_times = models.BooleanField(blank=True, null=True)
    t1_percent = models.FloatField(blank=True, null=True)
    t2_percent = models.FloatField(blank=True, null=True)
    interface_id = models.BinaryField(blank=True, null=True)
    min_preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    max_preferred_lifetime = models.BigIntegerField(blank=True, null=True)
    min_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    max_valid_lifetime = models.BigIntegerField(blank=True, null=True)
    ddns_send_updates = models.BooleanField(blank=True, null=True)
    ddns_override_no_update = models.BooleanField(blank=True, null=True)
    ddns_override_client_update = models.BooleanField(blank=True, null=True)
    ddns_replace_client_name = models.ForeignKey(DdnsReplaceClientNameTypes, models.DO_NOTHING, db_column='ddns_replace_client_name', blank=True, null=True)
    ddns_generated_prefix = models.CharField(max_length=255, blank=True, null=True)
    ddns_qualifying_suffix = models.CharField(max_length=255, blank=True, null=True)
    reservations_global = models.BooleanField(blank=True, null=True)
    reservations_in_subnet = models.BooleanField(blank=True, null=True)
    reservations_out_of_pool = models.BooleanField(blank=True, null=True)
    cache_threshold = models.FloatField(blank=True, null=True)
    cache_max_age = models.BigIntegerField(blank=True, null=True)
    allocator = models.TextField(blank=True, null=True)
    pd_allocator = models.TextField(blank=True, null=True)
    ddns_ttl_percent = models.FloatField(blank=True, null=True)
    ddns_ttl = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_min = models.BigIntegerField(blank=True, null=True)
    ddns_ttl_max = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp6_subnet'


class Dhcp6SubnetServer(models.Model):
    pk = models.CompositePrimaryKey('subnet_id', 'server_id')
    subnet = models.ForeignKey(Dhcp6Subnet, models.DO_NOTHING)
    server = models.ForeignKey(Dhcp6Server, models.DO_NOTHING)
    modification_ts = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'dhcp6_subnet_server'


class DhcpOptionScope(models.Model):
    scope_id = models.SmallIntegerField(primary_key=True)
    scope_name = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dhcp_option_scope'


class HostIdentifierType(models.Model):
    type = models.SmallIntegerField(primary_key=True)
    name = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'host_identifier_type'


class Hosts(models.Model):
    host_id = models.AutoField(primary_key=True)
    dhcp_identifier = models.BinaryField()
    dhcp_identifier_type = models.ForeignKey(HostIdentifierType, models.DO_NOTHING, db_column='dhcp_identifier_type')
    dhcp4_subnet_id = models.BigIntegerField(blank=True, null=True)
    dhcp6_subnet_id = models.BigIntegerField(blank=True, null=True)
    ipv4_address = models.BigIntegerField(blank=True, null=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    dhcp4_client_classes = models.CharField(max_length=255, blank=True, null=True)
    dhcp6_client_classes = models.CharField(max_length=255, blank=True, null=True)
    dhcp4_next_server = models.BigIntegerField(blank=True, null=True)
    dhcp4_server_hostname = models.CharField(max_length=64, blank=True, null=True)
    dhcp4_boot_file_name = models.CharField(max_length=128, blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)
    auth_key = models.CharField(max_length=32, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'hosts'
        unique_together = (('dhcp_identifier', 'dhcp_identifier_type', 'dhcp4_subnet_id'), ('dhcp_identifier', 'dhcp_identifier_type', 'dhcp6_subnet_id'),)


class Ipv6Reservations(models.Model):
    reservation_id = models.AutoField(primary_key=True)
    address = models.GenericIPAddressField()
    prefix_len = models.SmallIntegerField()
    type = models.SmallIntegerField()
    dhcp6_iaid = models.IntegerField(blank=True, null=True)
    host = models.ForeignKey(Hosts, models.DO_NOTHING)
    excluded_prefix = models.GenericIPAddressField(blank=True, null=True)
    excluded_prefix_len = models.SmallIntegerField()

    class Meta:
        managed = False
        db_table = 'ipv6_reservations'


class Lease4(models.Model):
    address = models.BigIntegerField(primary_key=True)
    hwaddr = models.BinaryField(blank=True, null=True)
    client_id = models.BinaryField(blank=True, null=True)
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    expire = models.DateTimeField(blank=True, null=True)
    subnet_id = models.BigIntegerField(blank=True, null=True)
    fqdn_fwd = models.BooleanField(blank=True, null=True)
    fqdn_rev = models.BooleanField(blank=True, null=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    state = models.ForeignKey('LeaseState', models.DO_NOTHING, db_column='state', blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)
    relay_id = models.BinaryField(blank=True, null=True)
    remote_id = models.BinaryField(blank=True, null=True)
    pool_id = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'lease4'


class Lease4PoolStat(models.Model):
    pk = models.CompositePrimaryKey('subnet_id', 'pool_id', 'state')
    subnet_id = models.BigIntegerField()
    pool_id = models.BigIntegerField()
    state = models.BigIntegerField()
    leases = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lease4_pool_stat'


class Lease4Stat(models.Model):
    pk = models.CompositePrimaryKey('subnet_id', 'state')
    subnet_id = models.BigIntegerField()
    state = models.BigIntegerField()
    leases = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lease4_stat'


class Lease4StatByClientClass(models.Model):
    client_class = models.CharField(primary_key=True, max_length=128)
    leases = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'lease4_stat_by_client_class'


class Lease6(models.Model):
    address = models.GenericIPAddressField(primary_key=True)
    duid = models.BinaryField(blank=True, null=True)
    valid_lifetime = models.BigIntegerField(blank=True, null=True)
    expire = models.DateTimeField(blank=True, null=True)
    subnet_id = models.BigIntegerField(blank=True, null=True)
    pref_lifetime = models.BigIntegerField(blank=True, null=True)
    lease_type = models.ForeignKey('Lease6Types', models.DO_NOTHING, db_column='lease_type', blank=True, null=True)
    iaid = models.IntegerField(blank=True, null=True)
    prefix_len = models.SmallIntegerField(blank=True, null=True)
    fqdn_fwd = models.BooleanField(blank=True, null=True)
    fqdn_rev = models.BooleanField(blank=True, null=True)
    hostname = models.CharField(max_length=255, blank=True, null=True)
    state = models.ForeignKey('LeaseState', models.DO_NOTHING, db_column='state', blank=True, null=True)
    hwaddr = models.BinaryField(blank=True, null=True)
    hwtype = models.SmallIntegerField(blank=True, null=True)
    hwaddr_source = models.SmallIntegerField(blank=True, null=True)
    user_context = models.TextField(blank=True, null=True)
    pool_id = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'lease6'


class Lease6PoolStat(models.Model):
    pk = models.CompositePrimaryKey('subnet_id', 'pool_id', 'lease_type', 'state')
    subnet_id = models.BigIntegerField()
    pool_id = models.BigIntegerField()
    lease_type = models.SmallIntegerField()
    state = models.BigIntegerField()
    leases = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lease6_pool_stat'


class Lease6RelayId(models.Model):
    extended_info_id = models.AutoField(primary_key=True)
    relay_id = models.BinaryField()
    lease_addr = models.ForeignKey(Lease6, models.DO_NOTHING, db_column='lease_addr')

    class Meta:
        managed = False
        db_table = 'lease6_relay_id'


class Lease6RemoteId(models.Model):
    extended_info_id = models.AutoField(primary_key=True)
    remote_id = models.BinaryField()
    lease_addr = models.ForeignKey(Lease6, models.DO_NOTHING, db_column='lease_addr')

    class Meta:
        managed = False
        db_table = 'lease6_remote_id'


class Lease6Stat(models.Model):
    pk = models.CompositePrimaryKey('subnet_id', 'lease_type', 'state')
    subnet_id = models.BigIntegerField()
    lease_type = models.SmallIntegerField()
    state = models.BigIntegerField()
    leases = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lease6_stat'


class Lease6StatByClientClass(models.Model):
    pk = models.CompositePrimaryKey('client_class', 'lease_type')
    client_class = models.CharField(max_length=128)
    lease_type = models.ForeignKey('Lease6Types', models.DO_NOTHING, db_column='lease_type')
    leases = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'lease6_stat_by_client_class'


class Lease6Types(models.Model):
    lease_type = models.SmallIntegerField(primary_key=True)
    name = models.CharField(max_length=5, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lease6_types'


class LeaseHwaddrSource(models.Model):
    hwaddr_source = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=40, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lease_hwaddr_source'


class LeaseState(models.Model):
    state = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=64)

    class Meta:
        managed = False
        db_table = 'lease_state'


class Logs(models.Model):
    timestamp = models.DateTimeField(blank=True, null=True)
    address = models.CharField(max_length=43, blank=True, null=True)
    log = models.TextField()

    class Meta:
        managed = False
        db_table = 'logs'


class Modification(models.Model):
    id = models.SmallIntegerField(primary_key=True)
    modification_type = models.CharField(max_length=32)

    class Meta:
        managed = False
        db_table = 'modification'


class OptionDefDataType(models.Model):
    id = models.SmallIntegerField(primary_key=True)
    name = models.CharField(max_length=32)

    class Meta:
        managed = False
        db_table = 'option_def_data_type'


class ParameterDataType(models.Model):
    id = models.SmallIntegerField(primary_key=True)
    name = models.CharField(max_length=32)

    class Meta:
        managed = False
        db_table = 'parameter_data_type'


class SchemaVersion(models.Model):
    version = models.IntegerField(primary_key=True)
    minor = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'schema_version'

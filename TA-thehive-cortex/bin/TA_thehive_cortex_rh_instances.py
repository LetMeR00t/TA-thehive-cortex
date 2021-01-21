import ta_thehive_cortex_declare

from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
    SingleModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunk_aoblib.rest_migration import ConfigMigrationHandler

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        'thehive_hostname',
        required=True,
        encrypted=False,
        default=None,
        validator=validator.Pattern(
            regex=r"""^[0-9a-zA-Z\-\.]+$""",
        )
    ),
    field.RestField(
        'thehive_port',
        required=True,
        encrypted=False,
        default=None,
        validator=validator.Number(
            max_val=65535,
            min_val=1,
        )
    ),
    field.RestField(
        'thehive_type',
        required=True,
        encrypted=False,
        default=None,
        validator=None
    ),
    field.RestField(
        'thehive_key',
        required=True,
        encrypted=True,
        default=None,
        validator=validator.String(
            max_len=8192,
            min_len=0,
        )
    ),
    field.RestField(
        'thehive_verifycert',
        required=False,
        encrypted=False,
        default=True,
        validator=None
    ),
    field.RestField(
        'thehive_ca_full_path',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=8192,
            min_len=0,
        )
    ),
    field.RestField(
        'thehive_use_proxy',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ),
    field.RestField(
        'client_use_cert',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ),
    field.RestField(
        'client_cert_full_path',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=8192,
            min_len=0,
        )
    )
]
model = RestModel(fields, name=None)


endpoint = SingleModel(
    'ta_thehive_cortex_instances',
    model,
)


if __name__ == '__main__':
    admin_external.handle(
        endpoint,
        handler=ConfigMigrationHandler,
    )

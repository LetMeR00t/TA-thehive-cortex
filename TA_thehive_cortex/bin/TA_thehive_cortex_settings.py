import ta_thehive_cortex_declare_lib
from TA_thehive_cortex_handler import CortexConfigurationHandler
import splunk.admin as admin
from splunktaucclib.rest_handler.endpoint import field, validator, RestModel, MultipleModel


fields_thehive = [
    field.RestField(
        'thehive_protocol',
        required=False,
        encrypted=False,
        default='http',
        validator=None
    ), 
    field.RestField(
        'thehive_host',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=4096, 
            min_len=0, 
        )
    ), 
    field.RestField(
        'thehive_port',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Number(
            max_val=65535, 
            min_val=1, 
        )
    ), 
    field.RestField(
        'thehive_api_key',
        required=False,
        encrypted=True,
        default=None,
        validator=validator.String(
            max_len=8192, 
            min_len=0, 
        )
    ),
    field.RestField(
        'thehive_jobs_max',
        required=True,
        encrypted=False,
        default="100",
        validator=validator.Number(
            max_val=1000, 
            min_val=1, 
        )
    ),
    field.RestField(
        'thehive_jobs_sort',
        required=True,
        encrypted=False,
        default="-startDate",
        validator=validator.String(
            max_len=512, 
            min_len=0, 
        )
    )

]
model_thehive = RestModel(fields_thehive, name='thehive')


fields_cortex = [
    field.RestField(
        'cortex_protocol',
        required=False,
        encrypted=False,
        default='http',
        validator=None
    ), 
    field.RestField(
        'cortex_host',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.String(
            max_len=4096, 
            min_len=0, 
        )
    ), 
    field.RestField(
        'cortex_port',
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Number(
            max_val=65535, 
            min_val=1, 
        )
    ), 
    field.RestField(
        'cortex_api_key',
        required=False,
        encrypted=True,
        default=None,
        validator=validator.String(
            max_len=8192, 
            min_len=0, 
        )
    ),
    field.RestField(
        'cortex_jobs_max',
        required=True,
        encrypted=False,
        default="100",
        validator=validator.Number(
            max_val=1000, 
            min_val=1, 
        )
    ),
    field.RestField(
        'cortex_jobs_sort',
        required=True,
        encrypted=False,
        default="-createdAt",
        validator=validator.String(
            max_len=512, 
            min_len=0, 
        )
    )
]
model_cortex = RestModel(fields_cortex, name='cortex')



#fields_proxy = [
#    field.RestField(
#        'proxy_enabled',
#        required=False,
#        encrypted=False,
#        default=None,
#        validator=None
#    ), 
#    field.RestField(
#        'proxy_type',
#        required=False,
#        encrypted=False,
#        default='http',
#        validator=None
#    ), 
#    field.RestField(
#        'proxy_url',
#        required=False,
#        encrypted=False,
#        default=None,
#        validator=validator.String(
#            max_len=4096, 
#            min_len=0, 
#        )
#    ), 
#    field.RestField(
#        'proxy_port',
#        required=False,
#        encrypted=False,
#        default=None,
#        validator=validator.Number(
#            max_val=65535, 
#            min_val=1, 
#        )
#    ), 
#    field.RestField(
#        'proxy_username',
#        required=False,
#        encrypted=False,
#        default=None,
#        validator=validator.String(
#            max_len=50, 
#            min_len=0, 
#        )
#    ), 
#    field.RestField(
#        'proxy_password',
#        required=False,
#        encrypted=True,
#        default=None,
#        validator=validator.String(
#            max_len=8192, 
#            min_len=0, 
#        )
#    ), 
#    field.RestField(
#        'proxy_rdns',
#        required=False,
#        encrypted=False,
#        default=None,
#        validator=None
#    )
#]
#model_proxy = RestModel(fields_proxy, name='proxy')


fields_logging = [
    field.RestField(
        'debug',
        required=False,
        encrypted=False,
        default=None,
        validator=None
    ) 
]
model_logging = RestModel(fields_logging, name='logging')




endpoint = MultipleModel(
    'ta_thehive_cortex_settings',
    models=[
        model_thehive,
        model_cortex,
#        model_proxy,
        model_logging
    ],
)


if __name__ == '__main__':

    handler = CortexConfigurationHandler

    final_handler = type(
        handler.__name__,
        (handler, ),
        {'endpoint': endpoint},
    )

    # initialize the handler
    admin.init(final_handler, admin.CONTEXT_APP_AND_USER)

"""drf-spectacular extensions.

Importing this module is what registers them; core/apps.py does that from
ready() so the schema generator always sees them.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ArcJWTScheme(OpenApiAuthenticationExtension):
    """Teach the schema generator about accounts.authentication.ArcJWTAuthentication.

    Without this, drf-spectacular cannot tell how the custom authenticator
    expects credentials, so it omits the security requirement and Swagger UI
    renders no Authorize button at all.
    """

    target_class = 'accounts.authentication.ArcJWTAuthentication'
    name = 'arcJWT'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': (
                'A full-scope access token from POST /api/auth/login/mfa/. '
                'The mfa_pending token from the first login step is rejected '
                'everywhere else.'
            ),
        }

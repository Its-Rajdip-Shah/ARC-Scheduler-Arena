"""A thin read-only client for the Canvas LMS REST API (FR-04, FR-05).

Only the three endpoints ARC needs are wrapped. Everything is returned as the
raw decoded JSON so the sync service, not this module, decides what a missing
field means: Canvas legitimately omits due dates, points and course codes, and
inventing values here would put guesses into the user's planner.
"""

import requests
from requests import RequestException

#: Canvas paginates at 10 by default and caps at 100.
PAGE_SIZE = 100

#: Canvas is sometimes slow on a cold course listing.
TIMEOUT_SECONDS = 20


class CanvasError(Exception):
    """A Canvas request that ARC cannot recover from.

    ``status`` is the HTTP status Canvas returned, or None when the request
    never got that far, which is the difference between a bad token and an
    unreachable host.
    """

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class CanvasClient:
    def __init__(self, base_url, api_token, session=None):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.session = session or requests.Session()

    def _get(self, path, params=None):
        url = f'{self.base_url}/api/v1{path}'
        try:
            response = self.session.get(
                url,
                headers={'Authorization': f'Bearer {self.api_token}'},
                params={'per_page': PAGE_SIZE, **(params or {})},
                timeout=TIMEOUT_SECONDS,
            )
        except RequestException as exc:
            raise CanvasError(f'Could not reach Canvas: {exc}') from exc

        if response.status_code == 401:
            raise CanvasError('Canvas rejected the API token.', status=401)
        if response.status_code == 403:
            raise CanvasError(
                'The token is valid but lacks permission for this data.', status=403
            )
        if not response.ok:
            raise CanvasError(
                f'Canvas returned {response.status_code}.', status=response.status_code
            )

        try:
            return response.json()
        except ValueError as exc:
            raise CanvasError('Canvas returned a response that was not JSON.') from exc

    def whoami(self):
        """Confirm the token works, and identify whose it is (FR-04)."""
        return self._get('/users/self')

    def courses(self):
        """Active courses for the token holder."""
        return self._get(
            '/courses', {'enrollment_state': 'active', 'state[]': 'available'}
        )

    def assignments(self, course_id):
        return self._get(f'/courses/{course_id}/assignments')

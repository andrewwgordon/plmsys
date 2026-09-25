"""Route-level security: Setup views are permission-protected, not just hidden.

The menu hides Setup for non-admins via both FAB's ``menu_access`` permission
and the ``menu_cond`` guard; these tests assert the routes themselves reject
non-admins (defence in depth).
"""

import pytest

SETUP_ROUTES = [
    "/objecttypemodelview/list/",
    "/propertydefinitionmodelview/list/",
    "/relationshiptypemodelview/list/",
    "/revisionrulemodelview/list/",
    "/releasestatemodelview/list/",
    "/revisionlineagemodelview/list/",
    "/propertyvaluemodelview/list/",
    "/baselinemembermodelview/list/",
    "/revisionreleasestatemodelview/list/",
]


@pytest.mark.parametrize("url", SETUP_ROUTES)
def test_viewer_cannot_reach_setup_route(viewer_client, url):
    assert viewer_client.get(url, follow_redirects=False).status_code == 403


@pytest.mark.parametrize("url", SETUP_ROUTES)
def test_admin_can_reach_setup_route(admin_client, url):
    assert admin_client.get(url, follow_redirects=False).status_code == 200

from .models import Group, RolePermission, UserGroupRelation

PERMISSION_FIELDS = [
    'can_invite_user',
    'can_remove_member',
    'can_manage_role',
    'can_edit_group',
    'can_edit_schedule',
    'can_manage_subject',
    'can_manage_tag',
    'can_manage_webhook',
]

_ALL_TRUE = {field: True for field in PERMISSION_FIELDS}
_ALL_FALSE = {field: False for field in PERMISSION_FIELDS}


def get_group_permissions(user, group: Group) -> dict:
    """
    Return a dict of all permission booleans for a user within a group.
    Owner implicitly holds all permissions, bypassing role checks.
    """
    if str(group.owner_id) == str(user.id):
        return _ALL_TRUE.copy()

    role_perms = RolePermission.objects.filter(
        role__userrelations__user=user,
        role__group=group,
    )

    if not role_perms.exists():
        return _ALL_FALSE.copy()

    result = {}
    for field in PERMISSION_FIELDS:
        result[field] = role_perms.filter(**{field: True}).exists()
    return result


def is_group_member(user, group: Group) -> bool:
    return UserGroupRelation.objects.filter(
        user=user,
        group=group,
        status=UserGroupRelation.Status.JOINED,
    ).exists()


def assert_is_member(user, group: Group):
    """Raises ValueError if user is not an active group member (and not the owner)."""
    if str(group.owner_id) == str(user.id):
        return
    if not is_group_member(user, group):
        raise PermissionError('You are not a member of this group.')


def has_permission(user, group: Group, perm: str) -> bool:
    """Return True if the user has the given permission in the group."""
    if str(group.owner_id) == str(user.id):
        return True
    return RolePermission.objects.filter(
        **{perm: True},
        role__userrelations__user=user,
        role__group=group,
    ).exists()

from django.urls import path

from .views import (
    AssignRoleView,
    BannedMemberListView,
    GroupApproveView,
    GroupBanView,
    GroupDetailView,
    GroupInviteView,
    GroupJoinView,
    GroupLeaveView,
    GroupListCreateView,
    GroupMemberListView,
    GroupRemoveMemberView,
    GroupTransferView,
    InviteAcceptView,
    InviteDeleteView,
    InviteListView,
    MyPermissionsView,
    PendingMemberListView,
    RemoveRoleView,
    RoleDetailView,
    RoleListCreateView,
    SubjectDetailView,
    SubjectListCreateView,
    TagDetailView,
    TagListCreateView,
    TagReorderView,
    WebhookDetailView,
    WebhookListCreateView,
)

urlpatterns = [
    # Groups
    path('groups/', GroupListCreateView.as_view(), name='group-list-create'),
    path('groups/<uuid:group_id>/', GroupDetailView.as_view(), name='group-detail'),
    path('groups/<uuid:group_id>/transfer/', GroupTransferView.as_view(), name='group-transfer'),
    path('groups/<uuid:group_id>/leave/', GroupLeaveView.as_view(), name='group-leave'),

    # Member management
    path('groups/<uuid:group_id>/members/', GroupMemberListView.as_view(), name='group-member-list'),
    path('groups/<uuid:group_id>/join/', GroupJoinView.as_view(), name='group-join'),
    path('groups/<uuid:group_id>/approve/<uuid:user_id>/', GroupApproveView.as_view(), name='group-approve'),
    path('groups/<uuid:group_id>/members/<uuid:user_id>/', GroupRemoveMemberView.as_view(), name='group-remove-member'),
    path('groups/<uuid:group_id>/ban/<uuid:user_id>/', GroupBanView.as_view(), name='group-ban'),

    # Invitations
    path('groups/<uuid:group_id>/invite/', GroupInviteView.as_view(), name='group-invite'),
    path('invites/', InviteListView.as_view(), name='invite-list'),
    path('invites/<uuid:invite_id>/accept/', InviteAcceptView.as_view(), name='invite-accept'),
    path('invites/<uuid:invite_id>/', InviteDeleteView.as_view(), name='invite-delete'),

    # Roles
    path('groups/<uuid:group_id>/roles/', RoleListCreateView.as_view(), name='role-list-create'),
    path('groups/<uuid:group_id>/roles/<uuid:role_id>/', RoleDetailView.as_view(), name='role-detail'),
    path('groups/<uuid:group_id>/members/<uuid:user_id>/roles/', AssignRoleView.as_view(), name='assign-role'),
    path('groups/<uuid:group_id>/members/<uuid:user_id>/roles/<uuid:role_id>/', RemoveRoleView.as_view(), name='remove-role'),

    # My permissions & member status lists
    path('groups/<uuid:group_id>/my-permissions/', MyPermissionsView.as_view(), name='my-permissions'),
    path('groups/<uuid:group_id>/pending-members/', PendingMemberListView.as_view(), name='pending-members'),
    path('groups/<uuid:group_id>/banned-members/', BannedMemberListView.as_view(), name='banned-members'),

    # Subjects & Tags
    path('groups/<uuid:group_id>/subjects/', SubjectListCreateView.as_view(), name='subject-list-create'),
    path('groups/<uuid:group_id>/subjects/<uuid:subject_id>/', SubjectDetailView.as_view(), name='subject-detail'),
    path('groups/<uuid:group_id>/tags/', TagListCreateView.as_view(), name='tag-list-create'),
    path('groups/<uuid:group_id>/tags/reorder/', TagReorderView.as_view(), name='tag-reorder'),
    path('groups/<uuid:group_id>/tags/<uuid:tag_id>/', TagDetailView.as_view(), name='tag-detail'),

    # Webhooks
    path('groups/<uuid:group_id>/webhooks/', WebhookListCreateView.as_view(), name='webhook-list-create'),
    path('groups/<uuid:group_id>/webhooks/<uuid:webhook_id>/', WebhookDetailView.as_view(), name='webhook-detail'),
]

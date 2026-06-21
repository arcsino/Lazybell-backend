from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from common.moderation import ModerationError, check_moderation
from common.throttles import InviteRateThrottle
from common.webhooks import decrypt_url, encrypt_url, test_webhook

from .models import (
    Group,
    GroupRole,
    GroupWebhook,
    InvitedGroupRelation,
    RolePermission,
    Subject,
    Tag,
    UserGroupRelation,
    UserRoleRelation,
)
from .permissions import has_permission, is_group_member
from .serializers import (
    AssignRoleSerializer,
    GroupCreateSerializer,
    GroupPendingInviteSerializer,
    GroupRoleCreateSerializer,
    GroupRoleSerializer,
    GroupRoleUpdateSerializer,
    GroupSerializer,
    GroupUpdateSerializer,
    InviteSerializer,
    MemberRelationSerializer,
    SubjectSerializer,
    TagReorderSerializer,
    TagSerializer,
    WebhookCreateSerializer,
    WebhookSerializer,
    WebhookUpdateSerializer,
)


def _get_active_group(group_id):
    return get_object_or_404(Group, id=group_id, is_deleted=False)


def _require_membership(user, group):
    """Return 403 response if user is not a member. Returns None if OK."""
    if not (str(group.owner_id) == str(user.id) or is_group_member(user, group)):
        return Response({'error': 'You are not a member of this group.'}, status=status.HTTP_403_FORBIDDEN)
    return None


def _require_permission(user, group, perm):
    """Return 403 response if user lacks the permission. Returns None if OK."""
    if not has_permission(user, group, perm):
        return Response({'error': 'You do not have permission to perform this action.'}, status=status.HTTP_403_FORBIDDEN)
    return None


# ── Group CRUD ────────────────────────────────────────────────────────────────


class GroupListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        joined_group_ids = UserGroupRelation.objects.filter(
            user=user, status=UserGroupRelation.Status.JOINED
        ).values_list('group_id', flat=True)
        owned_group_ids = Group.objects.filter(owner=user, is_deleted=False).values_list('id', flat=True)

        member_ids = set(joined_group_ids) | set(owned_group_ids)

        groups = Group.objects.filter(is_deleted=False).filter(
            Q(is_private=False) | Q(id__in=member_ids)
        ).select_related('owner').order_by('-created_at')

        serializer = GroupSerializer(groups, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            group = Group.objects.create(
                owner=request.user,
                **serializer.validated_data,
            )
            UserGroupRelation.objects.create(
                user=request.user,
                group=group,
                status=UserGroupRelation.Status.JOINED,
                joined_at=group.created_at,
            )

        return Response(GroupSerializer(group, context={'request': request}).data, status=status.HTTP_201_CREATED)


class GroupDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_group_or_404(self, request, group_id):
        group = get_object_or_404(Group, id=group_id, is_deleted=False)
        if group.is_private:
            user = request.user
            is_owner = str(group.owner_id) == str(user.id)
            if not is_owner and not is_group_member(user, group):
                return None, Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return group, None

    def get(self, request, group_id):
        group, err = self._get_group_or_404(request, group_id)
        if err:
            return err
        return Response(GroupSerializer(group, context={'request': request}).data)

    def patch(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_edit_group')
        if err:
            return err

        serializer = GroupUpdateSerializer(group, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(GroupSerializer(group, context={'request': request}).data)

    def delete(self, request, group_id):
        group = _get_active_group(group_id)
        if str(group.owner_id) != str(request.user.id):
            return Response({'error': 'Only the group owner can delete the group.'}, status=status.HTTP_403_FORBIDDEN)

        group.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupTransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        if str(group.owner_id) != str(request.user.id):
            return Response({'error': 'Only the owner can transfer ownership.'}, status=status.HTTP_403_FORBIDDEN)

        new_owner_id = request.data.get('user_id')
        if not new_owner_id:
            return Response({'error': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not is_group_member(User.objects.filter(id=new_owner_id).first() or User(), group):
            new_member = UserGroupRelation.objects.filter(
                group=group,
                user_id=new_owner_id,
                status=UserGroupRelation.Status.JOINED,
            ).first()
            if not new_member:
                return Response(
                    {'error': 'The specified user is not an active member of this group.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            new_owner = User.objects.get(id=new_owner_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not UserGroupRelation.objects.filter(
            group=group, user=new_owner, status=UserGroupRelation.Status.JOINED
        ).exists():
            return Response(
                {'error': 'The specified user is not an active member of this group.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group.owner = new_owner
        group.save(update_fields=['owner'])
        return Response(GroupSerializer(group, context={'request': request}).data)


class GroupLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, group_id):
        group = _get_active_group(group_id)
        user = request.user

        if str(group.owner_id) == str(user.id):
            return Response(
                {'error': 'The owner cannot leave the group without transferring ownership first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        relation = UserGroupRelation.objects.filter(
            user=user,
            group=group,
            status=UserGroupRelation.Status.JOINED,
        ).first()

        if not relation:
            return Response({'error': 'You are not a member of this group.'}, status=status.HTTP_400_BAD_REQUEST)

        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Member management ─────────────────────────────────────────────────────────


class GroupJoinView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        user = request.user

        if group.is_private:
            return Response({'error': 'This is a private group. You must be invited.'}, status=status.HTTP_403_FORBIDDEN)

        if str(group.owner_id) == str(user.id):
            return Response({'error': 'You are already the owner of this group.'}, status=status.HTTP_400_BAD_REQUEST)

        existing = UserGroupRelation.objects.filter(user=user, group=group).first()
        if existing:
            if existing.status == UserGroupRelation.Status.JOINED:
                return Response({'error': 'You are already a member.'}, status=status.HTTP_400_BAD_REQUEST)
            if existing.status == UserGroupRelation.Status.BANNED:
                return Response({'error': 'You are banned from this group.'}, status=status.HTTP_403_FORBIDDEN)
            if existing.status == UserGroupRelation.Status.REQUEST_PENDING:
                return Response({'error': 'Your join request is already pending.'}, status=status.HTTP_400_BAD_REQUEST)

        if group.max_members is not None:
            current_count = group.member_relations.filter(status=UserGroupRelation.Status.JOINED).count()
            if current_count >= group.max_members:
                return Response({'error': 'This group has reached its member limit.'}, status=status.HTTP_400_BAD_REQUEST)

        relation = UserGroupRelation.objects.create(
            user=user,
            group=group,
            status=UserGroupRelation.Status.REQUEST_PENDING,
        )
        return Response(MemberRelationSerializer(relation).data, status=status.HTTP_201_CREATED)


class GroupApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id, user_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_invite_user')
        if err:
            return err

        relation = get_object_or_404(
            UserGroupRelation,
            group=group,
            user_id=user_id,
            status=UserGroupRelation.Status.REQUEST_PENDING,
        )

        if group.max_members is not None:
            current_count = group.member_relations.filter(status=UserGroupRelation.Status.JOINED).count()
            if current_count >= group.max_members:
                return Response({'error': 'This group has reached its member limit.'}, status=status.HTTP_400_BAD_REQUEST)

        relation.approve()
        return Response(MemberRelationSerializer(relation).data)


class GroupRemoveMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, group_id, user_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_remove_member')
        if err:
            return err

        if str(user_id) == str(group.owner_id):
            return Response({'error': 'Cannot remove the group owner.'}, status=status.HTTP_400_BAD_REQUEST)

        relation = get_object_or_404(
            UserGroupRelation,
            group=group,
            user_id=user_id,
            status=UserGroupRelation.Status.JOINED,
        )
        UserRoleRelation.objects.filter(user_id=user_id, role__group=group).delete()
        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupBanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id, user_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_remove_member')
        if err:
            return err

        if str(user_id) == str(group.owner_id):
            return Response({'error': 'Cannot ban the group owner.'}, status=status.HTTP_400_BAD_REQUEST)

        if str(user_id) == str(request.user.id):
            return Response({'error': 'Cannot ban yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        relation = get_object_or_404(UserGroupRelation, group=group, user_id=user_id)

        if relation.status == UserGroupRelation.Status.BANNED:
            return Response({'error': 'User is already banned.'}, status=status.HTTP_400_BAD_REQUEST)

        UserRoleRelation.objects.filter(user_id=user_id, role__group=group).delete()
        relation.status = UserGroupRelation.Status.BANNED
        relation.joined_at = None
        relation.save(update_fields=['status', 'joined_at'])
        return Response(MemberRelationSerializer(relation).data)

    def delete(self, request, group_id, user_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_remove_member')
        if err:
            return err

        relation = get_object_or_404(
            UserGroupRelation,
            group=group,
            user_id=user_id,
            status=UserGroupRelation.Status.BANNED,
        )
        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BannedMemberListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_remove_member')
        if err:
            return err

        relations = group.member_relations.filter(
            status=UserGroupRelation.Status.BANNED
        ).select_related('user').order_by('user__nickname')
        return Response(MemberRelationSerializer(relations, many=True).data)


# ── Invitations ───────────────────────────────────────────────────────────────


class GroupInviteView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [InviteRateThrottle]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_invite_user')
        if err:
            return err
        invites = InvitedGroupRelation.objects.filter(
            group=group
        ).select_related('user', 'invited_by').order_by('-created_at')
        return Response(GroupPendingInviteSerializer(invites, many=True).data)

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_invite_user')
        if err:
            return err

        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if str(target_user.id) == str(group.owner_id):
            return Response({'error': 'Cannot invite the group owner.'}, status=status.HTTP_400_BAD_REQUEST)

        if UserGroupRelation.objects.filter(
            user=target_user, group=group, status=UserGroupRelation.Status.JOINED
        ).exists():
            return Response({'error': 'User is already a member of this group.'}, status=status.HTTP_400_BAD_REQUEST)

        if UserGroupRelation.objects.filter(
            user=target_user, group=group, status=UserGroupRelation.Status.BANNED
        ).exists():
            return Response({'error': 'User is banned from this group.'}, status=status.HTTP_400_BAD_REQUEST)

        if InvitedGroupRelation.objects.filter(user=target_user, group=group).exists():
            return Response({'error': 'User has already been invited.'}, status=status.HTTP_400_BAD_REQUEST)

        if group.max_members is not None:
            current_count = group.member_relations.filter(status=UserGroupRelation.Status.JOINED).count()
            if current_count >= group.max_members:
                return Response({'error': 'This group has reached its member limit.'}, status=status.HTTP_400_BAD_REQUEST)

        invite = InvitedGroupRelation.objects.create(
            user=target_user,
            group=group,
            invited_by=request.user,
        )
        return Response(InviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class GroupInviteCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, group_id, invite_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_invite_user')
        if err:
            return err
        invite = get_object_or_404(InvitedGroupRelation, id=invite_id, group=group)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InviteListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        invites = InvitedGroupRelation.objects.filter(
            user=request.user,
        ).select_related('group', 'group__owner', 'invited_by').order_by('-created_at')
        return Response(InviteSerializer(invites, many=True).data)


class InviteAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invite_id):
        invite = get_object_or_404(InvitedGroupRelation, id=invite_id, user=request.user)
        group = invite.group

        if group.is_deleted:
            invite.delete()
            return Response({'error': 'This group no longer exists.'}, status=status.HTTP_404_NOT_FOUND)

        if group.max_members is not None:
            current_count = group.member_relations.filter(status=UserGroupRelation.Status.JOINED).count()
            if current_count >= group.max_members:
                return Response({'error': 'This group has reached its member limit.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            relation, _ = UserGroupRelation.objects.get_or_create(
                user=request.user,
                group=group,
                defaults={'status': UserGroupRelation.Status.JOINED},
            )
            if relation.status == UserGroupRelation.Status.BANNED:
                invite.delete()
                return Response({'error': 'You are banned from this group.'}, status=status.HTTP_403_FORBIDDEN)

            relation.approve()
            invite.delete()

        return Response(MemberRelationSerializer(relation).data)


class InviteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, invite_id):
        invite = get_object_or_404(InvitedGroupRelation, id=invite_id, user=request.user)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Roles & Permissions ───────────────────────────────────────────────────────


class RoleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_membership(request.user, group)
        if err:
            return err
        roles = group.roles.prefetch_related('permission').order_by('name')
        return Response(GroupRoleSerializer(roles, many=True).data)

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_role')
        if err:
            return err

        serializer = GroupRoleCreateSerializer(data=request.data, context={'group': group})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            role = GroupRole.objects.create(name=data['name'], group=group)
            RolePermission.objects.create(role=role, **data['permission'])

        return Response(GroupRoleSerializer(role).data, status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_id, role_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_role')
        if err:
            return err

        role = get_object_or_404(GroupRole, id=role_id, group=group)
        serializer = GroupRoleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            if 'name' in data:
                role.name = data['name']
                role.save(update_fields=['name'])
            if 'permission' in data:
                perm_data = data['permission']
                RolePermission.objects.filter(role=role).update(**perm_data)

        role.refresh_from_db()
        return Response(GroupRoleSerializer(role).data)

    def delete(self, request, group_id, role_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_role')
        if err:
            return err

        role = get_object_or_404(GroupRole, id=role_id, group=group)
        role.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id, user_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_role')
        if err:
            return err

        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = get_object_or_404(GroupRole, id=serializer.validated_data['role_id'], group=group)

        if not UserGroupRelation.objects.filter(
            user_id=user_id, group=group, status=UserGroupRelation.Status.JOINED
        ).exists():
            if str(user_id) != str(group.owner_id):
                return Response(
                    {'error': 'Target user is not an active member of this group.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        relation, created = UserRoleRelation.objects.get_or_create(
            user_id=user_id,
            role=role,
            defaults={'assigned_by': request.user},
        )

        if not created:
            return Response({'error': 'User already has this role.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Role assigned successfully.'}, status=status.HTTP_201_CREATED)


class RemoveRoleView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, group_id, user_id, role_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_role')
        if err:
            return err

        relation = get_object_or_404(
            UserRoleRelation,
            user_id=user_id,
            role_id=role_id,
            role__group=group,
        )
        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Subjects & Tags ───────────────────────────────────────────────────────────


class SubjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_membership(request.user, group)
        if err:
            return err
        subjects = group.subjects.order_by('name')
        return Response(SubjectSerializer(subjects, many=True).data)

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_subject')
        if err:
            return err

        serializer = SubjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            check_moderation([serializer.validated_data['name']])
        except ModerationError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        subject = Subject.objects.create(group=group, **serializer.validated_data)
        return Response(SubjectSerializer(subject).data, status=status.HTTP_201_CREATED)


class SubjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_id, subject_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_subject')
        if err:
            return err

        subject = get_object_or_404(Subject, id=subject_id, group=group)
        serializer = SubjectSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_name = serializer.validated_data.get('name')
        if new_name is None:
            return Response(SubjectSerializer(subject).data)

        if new_name != subject.name:
            try:
                check_moderation([new_name])
            except ModerationError as e:
                return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            subject.name = new_name
            subject.save(update_fields=['name'])

        return Response(SubjectSerializer(subject).data)

    def delete(self, request, group_id, subject_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_subject')
        if err:
            return err

        subject = get_object_or_404(Subject, id=subject_id, group=group)
        subject.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_membership(request.user, group)
        if err:
            return err
        tags = group.tags.all()
        return Response(TagSerializer(tags, many=True).data)

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_tag')
        if err:
            return err

        serializer = TagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            check_moderation([serializer.validated_data['name']])
        except ModerationError as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        max_priority = group.tags.count()
        tag = Tag.objects.create(
            group=group,
            name=serializer.validated_data['name'],
            color=serializer.validated_data.get('color', '#6B7280'),
            priority=max_priority,
        )
        return Response(TagSerializer(tag).data, status=status.HTTP_201_CREATED)


class TagDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_id, tag_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_tag')
        if err:
            return err

        tag = get_object_or_404(Tag, id=tag_id, group=group)
        serializer = TagSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        update_fields = []
        new_name = serializer.validated_data.get('name')
        if new_name is not None and new_name != tag.name:
            try:
                check_moderation([new_name])
            except ModerationError as e:
                return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            tag.name = new_name
            update_fields.append('name')

        new_color = serializer.validated_data.get('color')
        if new_color:
            tag.color = new_color
            update_fields.append('color')

        if update_fields:
            tag.save(update_fields=update_fields)
        return Response(TagSerializer(tag).data)

    def delete(self, request, group_id, tag_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_tag')
        if err:
            return err

        tag = get_object_or_404(Tag, id=tag_id, group=group)
        tag.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_tag')
        if err:
            return err

        serializer = TagReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data['order']

        tags_map = {t.id: t for t in Tag.objects.filter(group=group)}
        for tag_id in order:
            if tag_id not in tags_map:
                return Response({'error': f'Tag {tag_id} not found.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for i, tag_id in enumerate(order):
                tags_map[tag_id].priority = i
            Tag.objects.bulk_update(list(tags_map[tid] for tid in order), ['priority'])

        updated = Tag.objects.filter(group=group)
        return Response(TagSerializer(updated, many=True).data)


# ── Member list ───────────────────────────────────────────────────────────────


class GroupMemberListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_membership(request.user, group)
        if err:
            return err

        relations = group.member_relations.filter(
            status=UserGroupRelation.Status.JOINED
        ).select_related('user').prefetch_related('user__role_relations__role').order_by('joined_at')
        return Response(MemberRelationSerializer(relations, many=True).data)


# ── My permissions ────────────────────────────────────────────────────────────


class MyPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        user = request.user
        is_owner = str(group.owner_id) == str(user.id)
        is_member = is_group_member(user, group)

        if group.is_private and not is_owner and not is_member:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        from .permissions import get_group_permissions
        perms = get_group_permissions(user, group)
        return Response({
            'is_owner': is_owner,
            'is_member': is_member or is_owner,
            **perms,
        })


class PendingMemberListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_invite_user')
        if err:
            return err

        relations = group.member_relations.filter(
            status=UserGroupRelation.Status.REQUEST_PENDING
        ).select_related('user').order_by('joined_at')
        return Response(MemberRelationSerializer(relations, many=True).data)


# ── Webhooks ──────────────────────────────────────────────────────────────────


class WebhookListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_webhook')
        if err:
            return err

        webhooks = group.webhooks.select_related('created_by', 'updated_by').order_by('created_at')
        return Response(WebhookSerializer(webhooks, many=True).data)

    def post(self, request, group_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_webhook')
        if err:
            return err

        serializer = WebhookCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not test_webhook(data['url']):
            return Response(
                {'error': 'Webhook URL test send failed. Verify the URL is correct and reachable.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        webhook = GroupWebhook.objects.create(
            group=group,
            webhook_type=data['webhook_type'],
            name=data.get('name', ''),
            encrypted_url=encrypt_url(data['url']),
            created_by=request.user,
            updated_by=request.user,
        )
        return Response(WebhookSerializer(webhook).data, status=status.HTTP_201_CREATED)


class WebhookDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, group_id, webhook_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_webhook')
        if err:
            return err

        webhook = get_object_or_404(GroupWebhook, id=webhook_id, group=group)
        serializer = WebhookUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = ['updated_by', 'updated_at']
        if 'url' in data:
            if not test_webhook(data['url']):
                return Response(
                    {'error': 'Webhook URL test send failed. Verify the URL is correct and reachable.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            webhook.encrypted_url = encrypt_url(data['url'])
            update_fields.append('encrypted_url')
        if 'name' in data:
            webhook.name = data['name']
            update_fields.append('name')

        webhook.updated_by = request.user
        webhook.save(update_fields=update_fields)
        return Response(WebhookSerializer(webhook).data)

    def delete(self, request, group_id, webhook_id):
        group = _get_active_group(group_id)
        err = _require_permission(request.user, group, 'can_manage_webhook')
        if err:
            return err

        webhook = get_object_or_404(GroupWebhook, id=webhook_id, group=group)
        webhook.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

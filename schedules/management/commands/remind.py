from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from common.webhooks import APP_NAME, _send_discord, build_remind_embed, decrypt_url
from groups.models import GroupWebhook
from schedules.models import Schedule

JST = ZoneInfo('Asia/Tokyo')


class Command(BaseCommand):
    help = 'Send remind webhooks for schedules due tomorrow (JST).'

    def handle(self, *args, **options):
        now_jst = timezone.now().astimezone(JST)
        tomorrow_start = datetime(now_jst.year, now_jst.month, now_jst.day, tzinfo=JST) + timedelta(days=1)
        tomorrow_end = tomorrow_start + timedelta(days=1) - timedelta(microseconds=1)

        schedules = (
            Schedule.objects.filter(
                is_deleted=False,
                deadline__gte=tomorrow_start,
                deadline__lte=tomorrow_end,
            )
            .select_related('group', 'subject', 'created_by')
            .prefetch_related('tag_relations__tag')
            .order_by('deadline')
        )

        by_group: dict[str, list] = {}
        for s in schedules:
            by_group.setdefault(str(s.group_id), []).append(s)

        if not by_group:
            self.stdout.write('No schedules due tomorrow.')
            return

        hooks_by_group: dict[str, list] = defaultdict(list)
        for h in GroupWebhook.objects.filter(
            group_id__in=by_group.keys(),
            webhook_type=GroupWebhook.WebhookType.REMIND,
        ):
            hooks_by_group[str(h.group_id)].append(h)

        sent = 0
        for group_id, group_schedules in by_group.items():
            hook_list = hooks_by_group.get(group_id, [])
            if not hook_list:
                continue

            embeds = [build_remind_embed(s) for s in group_schedules]
            for hook in hook_list:
                try:
                    url = decrypt_url(hook.encrypted_url)
                    for chunk_start in range(0, len(embeds), 10):
                        payload = {
                            'username': APP_NAME,
                            'content': '@everyone',
                            'embeds': embeds[chunk_start:chunk_start + 10],
                        }
                        ok = _send_discord(url, payload)
                        if not ok:
                            self.stderr.write(self.style.ERROR(
                                f'Failed to send remind webhook {hook.id} for group {group_id}'
                            ))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f'Error processing hook {hook.id} for group {group_id}: {e}'
                    ))
            sent += 1

        self.stdout.write(self.style.SUCCESS(
            f'Remind complete: {sent}/{len(by_group)} groups notified.'
        ))

        cutoff = timezone.now() - timedelta(weeks=1)
        deleted_count, _ = Schedule.objects.filter(
            is_deleted=True,
            deleted_at__lte=cutoff,
        ).delete()
        if deleted_count:
            self.stdout.write(f'Purged {deleted_count} old deleted schedule(s).')

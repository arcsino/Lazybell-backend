from django.conf import settings
from django.core.management import call_command
from rest_framework.response import Response
from rest_framework.views import APIView


class InternalRemindView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        expected = getattr(settings, "INTERNAL_API_KEY", "")
        if not expected or request.headers.get("X-Internal-Key") != expected:
            return Response({"detail": "Forbidden"}, status=403)
        call_command("remind")
        return Response({"status": "ok"})

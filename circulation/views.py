from django.urls import path
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from accounts.models import UserRole
from accounts.permissions import IsNotLocked, IsStaffOrAdmin
from circulation.exceptions import CirculationError
from circulation.models import Hold, Loan
from circulation.serializers import HoldSerializer, LoanSerializer
from circulation.services import checkout_copy, place_hold, renew_loan, return_copy


class LoanViewSet(ReadOnlyModelViewSet):
    serializer_class = LoanSerializer
    permission_classes = [IsNotLocked]

    def get_queryset(self):
        qs = Loan.objects.select_related("member", "copy", "copy__book").order_by("-loaned_at")
        user = self.request.user
        if user.role in (UserRole.ADMIN, UserRole.STAFF):
            return qs
        member_profile = getattr(user, "member_profile", None)
        if member_profile:
            return qs.filter(member=member_profile)
        return qs.none()


class HoldViewSet(ReadOnlyModelViewSet):
    serializer_class = HoldSerializer
    permission_classes = [IsNotLocked]

    def get_queryset(self):
        qs = Hold.objects.select_related("member", "book").order_by("book_id", "position")
        user = self.request.user
        if user.role in (UserRole.ADMIN, UserRole.STAFF):
            return qs
        member_profile = getattr(user, "member_profile", None)
        if member_profile:
            return qs.filter(member=member_profile)
        return qs.none()


@api_view(["POST"])
@permission_classes([IsStaffOrAdmin, IsNotLocked])
def checkout(request):
    try:
        loan = checkout_copy(
            member_no=request.data.get("member_no", ""),
            copy_barcode=request.data.get("copy_barcode", ""),
            loaned_by=request.user,
            source_screen="api.circulation.checkout",
        )
        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)
    except CirculationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsStaffOrAdmin, IsNotLocked])
def do_return(request):
    try:
        loan = return_copy(
            copy_barcode=request.data.get("copy_barcode", ""),
            returned_by=request.user,
            source_screen="api.circulation.return",
        )
        return Response(LoanSerializer(loan).data, status=status.HTTP_200_OK)
    except CirculationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsStaffOrAdmin, IsNotLocked])
def renew(request):
    try:
        loan = renew_loan(
            loan_id=int(request.data.get("loan_id")),
            renewed_by=request.user,
            source_screen="api.circulation.renew",
        )
        return Response(LoanSerializer(loan).data, status=status.HTTP_200_OK)
    except (CirculationError, TypeError, ValueError) as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsStaffOrAdmin, IsNotLocked])
def hold(request):
    try:
        h = place_hold(
            member_no=request.data.get("member_no", ""),
            book_id=int(request.data.get("book_id")),
        )
        return Response(HoldSerializer(h).data, status=status.HTTP_201_CREATED)
    except (CirculationError, TypeError, ValueError) as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


circulation_actions = [
    path("checkout/", checkout, name="checkout"),
    path("return/", do_return, name="return"),
    path("renew/", renew, name="renew"),
    path("hold/", hold, name="hold"),
]

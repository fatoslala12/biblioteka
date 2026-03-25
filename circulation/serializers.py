from rest_framework import serializers

from circulation.models import Hold, Loan


class LoanSerializer(serializers.ModelSerializer):
    copy_barcode = serializers.CharField(source="copy.barcode", read_only=True)
    book_title = serializers.CharField(source="copy.book.title", read_only=True)
    member_no = serializers.CharField(source="member.member_no", read_only=True)

    class Meta:
        model = Loan
        fields = (
            "id",
            "member",
            "member_no",
            "copy",
            "copy_barcode",
            "book_title",
            "status",
            "loaned_at",
            "due_at",
            "returned_at",
            "renew_count",
        )


class HoldSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)
    member_no = serializers.CharField(source="member.member_no", read_only=True)

    class Meta:
        model = Hold
        fields = (
            "id",
            "member",
            "member_no",
            "book",
            "book_title",
            "position",
            "status",
            "created_at",
            "ready_at",
            "expires_at",
        )

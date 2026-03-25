from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from accounts.models import MemberProfile


class ContactForm(forms.Form):
    name = forms.CharField(max_length=120, label="Emri")
    email = forms.EmailField(label="Email")
    subject = forms.CharField(max_length=160, label="Subjekti")
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}), label="Mesazhi")


class MemberProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = MemberProfile
        fields = [
            "photo",
            "full_name",
            "date_of_birth",
            "place_of_birth",
            "national_id",
            "phone",
            "address",
        ]
        labels = {
            "photo": "Foto",
            "full_name": "Emri dhe mbiemri",
            "date_of_birth": "Datëlindja",
            "place_of_birth": "Vendlindja",
            "national_id": "Nr. ID",
            "phone": "Nr. telefoni",
            "address": "Adresa",
        }
        widgets = {
            "photo": forms.ClearableFileInput(
                attrs={
                    "class": "mt-2 block w-full cursor-pointer rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm file:mr-4 file:rounded-xl file:border-0 file:bg-brand-700 file:px-4 file:py-2 file:text-xs file:font-extrabold file:text-white hover:file:bg-brand-800 dark:border-slate-800 dark:bg-slate-950"
                }
            ),
            "full_name": forms.TextInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40",
                }
            ),
            "place_of_birth": forms.TextInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
                }
            ),
            "national_id": forms.TextInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
                }
            ),
            "address": forms.TextInput(
                attrs={
                    "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
                }
            ),
        }


class MemberPasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        label="Fjalëkalimi aktual",
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
            }
        ),
    )
    new_password1 = forms.CharField(
        label="Fjalëkalimi i ri",
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
            }
        ),
    )
    new_password2 = forms.CharField(
        label="Përsërit fjalëkalimin e ri",
        widget=forms.PasswordInput(
            attrs={
                "class": "mt-2 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm outline-none focus:ring-4 focus:ring-brand-200 dark:border-slate-800 dark:bg-slate-950 dark:focus:ring-brand-900/40"
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_old_password(self):
        pw = self.cleaned_data.get("old_password") or ""
        if not self.user or not self.user.check_password(pw):
            raise ValidationError("Fjalëkalimi aktual është i pasaktë.")
        return pw

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password1") or ""
        p2 = cleaned.get("new_password2") or ""
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", "Fjalëkalimet nuk përputhen.")
            return cleaned
        if p1:
            password_validation.validate_password(p1, user=self.user)
        return cleaned


from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from accounts.models import MemberProfile, MemberStatus, MemberType, UserRole

User = get_user_model()

# Stil i njëjtë me faqen e hyrjes (Tailwind)
_AUTH_INPUT_CLASS = (
    "mt-2 w-full rounded-2xl border border-white/25 bg-white/10 px-4 py-3 text-sm "
    "text-white placeholder:text-white/70 outline-none focus:ring-4 focus:ring-white/20"
)


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


class MemberSignUpForm(forms.Form):
    """Regjistrim vetëm anëtarësh (MEMBER); të gjitha fushat e detyrueshme."""

    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={"class": _AUTH_INPUT_CLASS, "autocomplete": "email"}),
    )
    password1 = forms.CharField(
        label="Fjalëkalimi",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": _AUTH_INPUT_CLASS, "autocomplete": "new-password"}
        ),
    )
    password2 = forms.CharField(
        label="Përsërit fjalëkalimin",
        strip=False,
        widget=forms.PasswordInput(
            attrs={"class": _AUTH_INPUT_CLASS, "autocomplete": "new-password"}
        ),
    )
    full_name = forms.CharField(
        label="Emri dhe mbiemri",
        max_length=160,
        widget=forms.TextInput(attrs={"class": _AUTH_INPUT_CLASS, "autocomplete": "name"}),
    )
    phone = forms.CharField(
        label="Nr. telefoni",
        max_length=32,
        widget=forms.TextInput(attrs={"class": _AUTH_INPUT_CLASS, "autocomplete": "tel"}),
    )
    date_of_birth = forms.DateField(
        label="Datëlindja",
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": _AUTH_INPUT_CLASS + " sl-auth-date-input",
            }
        ),
    )
    national_id = forms.CharField(
        label="Nr. ID",
        max_length=32,
        widget=forms.TextInput(attrs={"class": _AUTH_INPUT_CLASS}),
    )
    place_of_birth = forms.CharField(
        label="Vendlindja",
        max_length=160,
        widget=forms.TextInput(attrs={"class": _AUTH_INPUT_CLASS}),
    )
    address = forms.CharField(
        label="Adresa",
        max_length=255,
        widget=forms.TextInput(attrs={"class": _AUTH_INPUT_CLASS, "autocomplete": "street-address"}),
    )
    # Honeypot (fshehur me CSS) – botët e mbushin
    company_website = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }
        ),
    )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if len(email) > 150:
            raise ValidationError(
                "Email-i është shumë i gjatë për përdorues në sistem (maks. 150 karaktere). "
                "Përdorni një adresë më të shkurtër."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ekziston tashmë një llogari me këtë email.")
        return email

    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        if not nid:
            raise ValidationError("Kjo fushë është e detyrueshme.")
        if MemberProfile.objects.filter(national_id__iexact=nid).exists():
            raise ValidationError("Ky numër ID është i regjistruar tashmë.")
        return nid

    def clean_company_website(self):
        if (self.cleaned_data.get("company_website") or "").strip():
            raise ValidationError("Dërgesa nuk u pranua.")
        return ""

    def clean_password1(self):
        p = self.cleaned_data.get("password1") or ""
        if len(p) < 10:
            raise ValidationError("Fjalëkalimi duhet të ketë të paktën 10 karaktere.")
        if len(p) > 128:
            raise ValidationError("Fjalëkalimi është shumë i gjatë.")
        if not any(c.isalpha() for c in p):
            raise ValidationError("Fjalëkalimi duhet të përmbajë të paktën një shkronjë.")
        if not any(c.isdigit() for c in p):
            raise ValidationError("Fjalëkalimi duhet të përmbajë të paktën një shifër (0–9).")
        return p

    def clean(self):
        data = super().clean()
        p1 = data.get("password1")
        p2 = data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Fjalëkalimet nuk përputhen.")
        return data


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


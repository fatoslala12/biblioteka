import re

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import MemberProfile, MemberStatus, MemberType, UserRole

User = get_user_model()

# Stil i njëjtë me faqen e hyrjes (Tailwind)
_AUTH_INPUT_CLASS = (
    "mt-2 w-full rounded-2xl border border-white/25 bg-white/10 px-4 py-3 text-sm "
    "text-white placeholder:text-white/70 outline-none focus:ring-4 focus:ring-white/20"
)
_AUTH_CHECKBOX_CLASS = (
    "h-5 w-5 rounded-md border border-white/40 bg-white/10 text-brand-200 "
    "focus:ring-2 focus:ring-white/35"
)
_AUTH_FILE_CLASS = (
    "mt-1 block w-full cursor-pointer rounded-xl border border-white/25 bg-white/90 px-3 py-2 "
    "text-xs font-semibold text-slate-800 file:mr-3 file:rounded-lg file:border-0 "
    "file:bg-brand-700 file:px-3 file:py-1.5 file:text-[11px] file:font-extrabold file:text-white "
    "hover:file:bg-brand-800"
)
_SIGNUP_PHOTO_MAX_BYTES = 5 * 1024 * 1024
_SIGNUP_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
_PERSONAL_NO_RE = re.compile(r"^[A-Z]\d{8}[A-Z]$")
_PERSONAL_NO_FORMAT_MSG = (
    "Lutem shkruani saktë nr. personal si në kartë të identitetit (shkronjë, 8 shifra, shkronjë)."
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
        widget=forms.EmailInput(
            attrs={
                "class": _AUTH_INPUT_CLASS,
                "autocomplete": "email",
                "placeholder": "emri@email.com",
            }
        ),
        error_messages={"required": "Email-i është i detyrueshëm."},
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
        label="Emër dhe mbiemër",
        max_length=160,
        widget=forms.TextInput(
            attrs={
                "class": _AUTH_INPUT_CLASS,
                "autocomplete": "name",
                "placeholder": "p.sh. Artan Cuku",
            }
        ),
    )
    phone = forms.CharField(
        label="Nr. telefoni",
        max_length=32,
        widget=forms.TextInput(
            attrs={
                "class": _AUTH_INPUT_CLASS,
                "autocomplete": "tel",
                "placeholder": "p.sh. 069 12 34 567",
            }
        ),
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
    photo = forms.ImageField(
        label="Foto profili",
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": _AUTH_FILE_CLASS,
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
    )
    national_id = forms.CharField(
        label="Numri personal",
        max_length=10,
        widget=forms.TextInput(
            attrs={
                "class": _AUTH_INPUT_CLASS + " sl-personal-no-input",
                "autocomplete": "off",
                "placeholder": "p.sh. J50408078S",
                "maxlength": "10",
                "spellcheck": "false",
            }
        ),
        error_messages={"required": "Numri personal është i detyrueshëm për regjistrim."},
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
    accept_terms = forms.BooleanField(
        label="Pranoj kushtet e përdorimit dhe privatësisë",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": _AUTH_CHECKBOX_CLASS}),
        error_messages={"required": "Duhet të pranoni kushtet për të vazhduar."},
    )
    # Hidden passive anti-bot fields. Do not block human users
    # aggressively (password managers can autofill unexpected inputs).
    trap_field = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={
                "tabindex": "-1",
                "autocomplete": "new-password",
                "aria-hidden": "true",
            }
        ),
    )
    signup_ts = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["signup_ts"] = str(int(timezone.now().timestamp()))

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("Shkruani adresën tuaj të email-it.")
        if len(email) > 150:
            raise ValidationError(
                "Email-i është shumë i gjatë (maks. 150 karaktere). Përdorni një adresë më të shkurtër."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "Ekziston tashmë një llogari me këtë email. Hyni me llogarinë ekzistuese ose përdorni një email tjetër."
            )
        if User.objects.filter(username__iexact=email).exists():
            raise ValidationError(
                "Ky email është i lidhur me një llogari ekzistuese. Provoni të hyni në vend që të regjistroheni përsëri."
            )
        return email

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if not photo:
            return None
        if photo.size > _SIGNUP_PHOTO_MAX_BYTES:
            raise ValidationError("Fotoja është shumë e madhe. Maksimumi i lejuar është 5 MB.")
        content_type = (getattr(photo, "content_type", "") or "").lower()
        if content_type and content_type not in _SIGNUP_PHOTO_TYPES:
            raise ValidationError("Formati i fotos nuk lejohet. Përdorni JPG, PNG ose WEBP.")
        return photo

    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip().upper()
        if not nid:
            raise ValidationError("Numri personal është i detyrueshëm për regjistrim.")
        if not _PERSONAL_NO_RE.match(nid):
            raise ValidationError(_PERSONAL_NO_FORMAT_MSG)
        if MemberProfile.objects.filter(national_id__iexact=nid).exists():
            raise ValidationError(
                "Me këtë numër personal ekziston tashmë një llogari. "
                "Nuk lejohet krijimi i dy llogarive me të njëjtin numër. "
                "Nëse keni llogari, hyrni me email-in tuaj."
            )
        return nid

    def clean_full_name(self):
        name = (self.cleaned_data.get("full_name") or "").strip()
        if not name:
            raise ValidationError("Shkruani emrin dhe mbiemrin tuaj.")
        if len(name) < 3:
            raise ValidationError("Emri dhe mbiemri duhet të kenë të paktën 3 karaktere.")
        return name

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            raise ValidationError("Shkruani numrin e telefonit.")
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 8:
            raise ValidationError("Numri i telefonit duket i pasaktë. Përdorni të paktën 8 shifra.")
        return phone

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if not dob:
            raise ValidationError("Zgjidhni datëlindjen tuaj.")
        today = timezone.localdate()
        if dob > today:
            raise ValidationError("Datëlindja nuk mund të jetë në të ardhmen.")
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 5:
            raise ValidationError("Datëlindja duket e pasaktë për regjistrim anëtari.")
        if age > 120:
            raise ValidationError("Datëlindja duket e pasaktë. Kontrolloni vitin e lindjes.")
        return dob

    def clean_place_of_birth(self):
        place = (self.cleaned_data.get("place_of_birth") or "").strip()
        if not place:
            raise ValidationError("Shkruani vendlindjen.")
        return place

    def clean_address(self):
        address = (self.cleaned_data.get("address") or "").strip()
        if not address:
            raise ValidationError("Shkruani adresën e banimit.")
        if len(address) < 5:
            raise ValidationError("Adresa duket shumë e shkurtër. Shkruani rrugën dhe qytetin.")
        return address

    def clean_signup_ts(self):
        raw = (self.cleaned_data.get("signup_ts") or "").strip()
        try:
            posted_ts = int(raw)
        except Exception:
            posted_ts = 0
        now_ts = int(timezone.now().timestamp())
        # Basic timing check: too fast submissions are likely automated.
        if posted_ts and (now_ts - posted_ts) < 1:
            raise ValidationError("Dërgesa shumë e shpejtë. Ju lutem provo përsëri.")
        return raw

    def clean_password1(self):
        p = self.cleaned_data.get("password1") or ""
        if not p:
            raise ValidationError("Shkruani një fjalëkalim.")
        if len(p) < 10:
            raise ValidationError("Fjalëkalimi duhet të ketë të paktën 10 karaktere.")
        if len(p) > 128:
            raise ValidationError("Fjalëkalimi është shumë i gjatë (maks. 128 karaktere).")
        if not any(c.isalpha() for c in p):
            raise ValidationError("Fjalëkalimi duhet të përmbajë të paktën një shkronjë.")
        if not any(c.isdigit() for c in p):
            raise ValidationError("Fjalëkalimi duhet të përmbajë të paktën një shifër (0–9).")
        return p

    def clean_password2(self):
        p2 = self.cleaned_data.get("password2") or ""
        if not p2:
            raise ValidationError("Përsëritni fjalëkalimin për konfirmim.")
        return p2

    def clean(self):
        data = super().clean()
        p1 = data.get("password1")
        p2 = data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error(
                "password2",
                "Fjalëkalimet nuk përputhen. Shkruani të njëjtin fjalëkalim në të dy fushat.",
            )
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


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": _AUTH_INPUT_CLASS,
                "autocomplete": "email",
                "placeholder": "email@shembull.com",
            }
        ),
    )


class MemberPasswordResetSetForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {
                "class": _AUTH_INPUT_CLASS,
                "autocomplete": "new-password",
                "placeholder": "Fjalëkalimi i ri",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "class": _AUTH_INPUT_CLASS,
                "autocomplete": "new-password",
                "placeholder": "Përsërit fjalëkalimin",
            }
        )


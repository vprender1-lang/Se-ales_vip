import re
from django import forms
from .models import Registration


class RegistrationForm(forms.ModelForm):
    accepted_review = forms.BooleanField(required=True)
    adult_confirmed = forms.BooleanField(required=True)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Registration
        fields = ['quotex_id', 'telegram_username', 'accepted_review', 'adult_confirmed']
        widgets = {
            'quotex_id': forms.TextInput(attrs={
                'inputmode': 'numeric', 'autocomplete': 'off', 'placeholder': 'Ej. 123456789',
                'maxlength': '20'
            }),
            'telegram_username': forms.TextInput(attrs={
                'autocomplete': 'off', 'placeholder': 'tuusuario', 'maxlength': '32'
            }),
        }

    def clean_quotex_id(self):
        value = self.cleaned_data['quotex_id'].strip()
        if not re.fullmatch(r'\d{5,20}', value):
            raise forms.ValidationError('Escribe un ID de Quotex válido usando solo números.')
        return value

    def clean_telegram_username(self):
        value = self.cleaned_data['telegram_username'].strip().lstrip('@')
        if not re.fullmatch(r'[A-Za-z0-9_]{5,32}', value):
            raise forms.ValidationError('Escribe un usuario de Telegram válido.')
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('website'):
            raise forms.ValidationError('Solicitud inválida.')
        return cleaned


class VipAccessForm(forms.Form):
    quotex_id = forms.CharField(
        label='ID de Quotex',
        min_length=5,
        max_length=20,
        widget=forms.TextInput(attrs={
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'placeholder': 'Ingresa tu ID aprobado',
            'maxlength': '20',
        }),
    )

    def clean_quotex_id(self):
        value = self.cleaned_data['quotex_id'].strip()
        if not re.fullmatch(r'\d{5,20}', value):
            raise forms.ValidationError('Escribe un ID de Quotex válido usando solo números.')
        return value

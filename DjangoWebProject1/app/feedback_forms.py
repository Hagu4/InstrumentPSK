from django import forms
from .models import Feedback

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['name', 'email', 'overall_rating', 'usability_rating', 'visit_frequency', 'comments']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ваше имя'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ваш email'}),
            'overall_rating': forms.HiddenInput(attrs={'id': 'id_overall_rating_hidden'}),
            'usability_rating': forms.RadioSelect,
            'visit_frequency': forms.RadioSelect,
            'comments': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Оставьте ваш комментарий здесь...'}),
        }
        labels = {
            'name': "Ваше имя",
            'email': "Email",
            'comments': "Комментарий",
        }
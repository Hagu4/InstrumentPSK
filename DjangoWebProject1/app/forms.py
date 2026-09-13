from django import forms
from django.db import transaction
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .uploads import prepare_images
from .models import Product, Review, Feedback, Profile, Order, ProductCharacteristic

from decimal import Decimal

# --- Восстановленные формы ---

class BootstrapAuthenticationForm(AuthenticationForm):
    """Authentication form with bootstrap classes."""
    username = forms.CharField(max_length=254,
                               widget=forms.TextInput({
                                   'class': 'form-control',
                                   'placeholder': 'Имя пользователя'}))
    password = forms.CharField(label="Пароль",
                               strip=False,
                               widget=forms.PasswordInput({
                                   'class': 'form-control',
                                   'placeholder': 'Пароль'}))

class BootstrapUserCreationForm(UserCreationForm):
    """User creation form with bootstrap classes."""
    def __init__(self, *args, **kwargs):
        super(BootstrapUserCreationForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class ExtendedRegistrationForm(forms.Form):
    first_name = forms.CharField(label='Имя', max_length=150, required=True)
    last_name = forms.CharField(label='Фамилия', max_length=150, required=False)
    phone_number = forms.CharField(label='Телефон', max_length=20, required=False)
    email = forms.EmailField(label='Email', required=True)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput, required=True)
    password2 = forms.CharField(label='Повторите пароль', widget=forms.PasswordInput, required=True)
    terms = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        super(ExtendedRegistrationForm, self).__init__(*args, **kwargs)
        # Применяем стили и плейсхолдеры
        self.fields['first_name'].widget.attrs.update({'placeholder': 'Иван'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Иванов'})
        self.fields['phone_number'].widget.attrs.update({'placeholder': '+7 (999) 000-00-00', 'type': 'tel'})
        self.fields['email'].widget.attrs.update({'placeholder': 'user@example.com'})
        # Добавляем класс для всех полей
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("Этот email уже используется.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password2 = cleaned_data.get("password2")

        if password and password2 and password != password2:
            self.add_error('password2', "Пароли не совпадают.")

        if password:
            candidate = User(
                username=cleaned_data.get('email', ''),
                email=cleaned_data.get('email', ''),
                first_name=cleaned_data.get('first_name', ''),
                last_name=cleaned_data.get('last_name', ''),
            )
            try:
                validate_password(password, user=candidate)
            except ValidationError as error:
                self.add_error('password', error)
        
        return cleaned_data

    @transaction.atomic
    def save(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        first_name = self.cleaned_data.get('first_name')
        last_name = self.cleaned_data.get('last_name')
        phone_number = self.cleaned_data.get('phone_number')

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        user.profile.phone_number = phone_number
        user.profile.save()

        return user



class ProductForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].label = "Цена со скидкой"
        self.fields['old_price'].label = "Старая цена (без скидки)"

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['prepared_images'] = prepare_images(self.files.getlist('images'), max_count=10)
        return cleaned_data

    class Meta:
        model = Product
        fields = ['title', 'sku', 'description', 'price', 'old_price', 'quantity', 'category', 'brand']
        widgets = {
            'title': forms.TextInput(),
            'sku': forms.TextInput(),
            'description': forms.Textarea(),
            'price': forms.NumberInput(),
            'old_price': forms.NumberInput(),
            'quantity': forms.NumberInput(),
            'category': forms.Select(),
            'brand': forms.Select(),
        }

class ReviewForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['prepared_images'] = prepare_images(self.files.getlist('review_images'), max_count=5)
        return cleaned_data

    pros = forms.CharField(
        label='Достоинства',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Что вам понравилось?',
            'rows': 2
        })
    )
    cons = forms.CharField(
        label='Недостатки',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Что не понравилось?',
            'rows': 2
        })
    )
    video_url = forms.URLField(
        label='Ссылка на видео',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://youtube.com/...'
        })
    )

    class Meta:
        model = Review
        fields = ['text', 'rating', 'pros', 'cons', 'video_url']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ваш отзыв', 'rows': 4}),
            'rating': forms.Select(choices=[(i, f'{i} звезд') for i in range(1, 6)], attrs={'class': 'form-control'}),
        }

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        exclude = ['created_at'] # Exclude fields that are set automatically
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'overall_rating': forms.Select(attrs={'class': 'form-control'}),
            'usability_rating': forms.Select(attrs={'class': 'form-control'}),
            'visit_frequency': forms.Select(attrs={'class': 'form-control'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        }
        
class ProfileForm(forms.ModelForm):
    # Add fields from the User model manually
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=True)

    class Meta:
        model = Profile
        fields = ['phone_number'] # Only fields from the Profile model here

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.instance is the profile object
        user = self.instance.user

        # Set initial values for the user fields
        self.fields['first_name'].initial = user.first_name
        self.fields['last_name'].initial = user.last_name
        self.fields['email'].initial = user.email

        # Apply widget attributes
        self.fields['phone_number'].widget.attrs.update({'class': 'form-control', 'placeholder': '+79001234567'})
        self.fields['first_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['last_name'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        # Save the profile part
        profile = super().save(commit=commit)
        
        # Save the user part
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            
        return profile

ProductCharacteristicFormSet = forms.inlineformset_factory(
    Product, 
    ProductCharacteristic,
    fields=('characteristic', 'value'),
    extra=1,
    widgets={
        'characteristic': forms.Select(),
        'value': forms.TextInput(),
    }
)

# --- Новые формы для оформления заказа ---

# Delivery costs can be moved to settings or a separate model later
DELIVERY_COSTS = {
    'PICKUP': Decimal('0.00'),
    'DELIVERY_POINT': Decimal('150.00'),
    'HOME_DELIVERY': Decimal('350.00'),
}

class DeliveryMethodForm(forms.Form):
    delivery_method = forms.ChoiceField(
        choices=Order.DELIVERY_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        error_messages={'required': 'Пожалуйста, выберите способ доставки.'}
    )

    def get_delivery_info(self):
        method = self.cleaned_data.get('delivery_method')
        cost = DELIVERY_COSTS.get(method, Decimal('0.00'))
        
        # This is a stub, in a real app you might calculate this based on address/provider
        if method == 'HOME_DELIVERY':
            timeframe = '1-2 рабочих дня'
        elif method == 'DELIVERY_POINT':
            timeframe = '2-4 рабочих дня'
        else:
            timeframe = 'готово к выдаче в течение дня'
            
        return {'cost': cost, 'timeframe': timeframe}


class DeliveryAddressForm(forms.Form):
    city = forms.CharField(
        label='Населенный пункт',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например, Псков'}),
        required=True
    )
    street = forms.CharField(
        label='Улица',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например, ул. Ленина'}),
        required=True
    )
    building = forms.CharField(
        label='Дом',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Дом, корпус, строение'}),
        required=True
    )
    apartment = forms.CharField(
        label='Квартира',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Кв./офис'}),
        required=False
    )
    postal_code = forms.CharField(
        label='Индекс',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123456'}),
        required=True
    )
    comment = forms.CharField(
        label='Комментарий курьеру',
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Код домофона, особенности проезда и т.д.'}),
        required=False
    )

    def get_full_address(self):
        """Constructs a full address string from the form fields."""
        if not self.is_valid():
            return ""
        
        data = self.cleaned_data
        address_parts = [
            data.get('postal_code'),
            data.get('city'),
            data.get('street'),
            data.get('building'),
            data.get('apartment')
        ]
        # Filter out empty parts and join
        return ", ".join(part for part in address_parts if part)

class PaymentMethodForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=Order.PAYMENT_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        error_messages={'required': 'Пожалуйста, выберите способ оплаты.'}
    )

    def __init__(self, *args, **kwargs):
        # Dynamically filter choices based on delivery method
        delivery_method = kwargs.pop('delivery_method', None)
        super().__init__(*args, **kwargs)
        
        if delivery_method != 'PICKUP':
            # For non-pickup, only online or on-delivery card payments are allowed
            self.fields['payment_method'].choices = [
                choice for choice in Order.PAYMENT_CHOICES 
                if choice[0] in ['CARD_ONLINE', 'CARD_ON_DELIVERY']
            ]


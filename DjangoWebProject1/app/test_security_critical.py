import io
import tempfile
from pathlib import Path

from PIL import Image
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .forms import ExtendedRegistrationForm, ProductCharacteristicFormSet
from .models import Category, Favorite, OrderItem, Product, ProductImage, Review


def photo(name='photo.png', size=(8, 8), trailer=b''):
    stream = io.BytesIO()
    Image.new('RGB', size, 'red').save(stream, format='PNG')
    return SimpleUploadedFile(name, stream.getvalue() + trailer, content_type='image/png')


class ProductSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.media = tempfile.TemporaryDirectory(prefix='instrumentpsk-tests-')
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create_user('buyer', password='Buyer-secure-713!')
        self.manager = User.objects.create_user('manager', password='Manager-secure-712!')
        self.manager.groups.add(Group.objects.get_or_create(name='Менеджер')[0])
        self.category = Category.objects.create(name='Tools', slug='security-tools')
        self.product = Product.objects.create(title='Existing tool', price='100.00', quantity=10, category=self.category)
        self.client.force_login(self.user)

    def product_data(self, images=()):
        prefix = ProductCharacteristicFormSet.get_default_prefix()
        return {'title': 'New tool', 'price': '100.00', 'quantity': '5',
                'category': str(self.category.pk), 'images': list(images),
                f'{prefix}-TOTAL_FORMS': '0', f'{prefix}-INITIAL_FORMS': '0',
                f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000'}

    def test_customer_cannot_open_product_creation(self):
        self.assertEqual(self.client.get('/add-product/').status_code, 403)

    def test_customer_cannot_create_product_or_file(self):
        response = self.client.post('/add-product/', self.product_data([photo()]))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Product.objects.filter(title='New tool').exists())
        self.assertEqual(list(Path(self.media.name).rglob('*')), [])

    def test_manager_can_create_product_with_normalized_photo(self):
        self.client.force_login(self.manager)
        marker = b'UNTRUSTED_TRAILING_CONTENT'
        response = self.client.post('/add-product/', self.product_data([photo(trailer=marker)]))
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(title='New tool')
        image = ProductImage.objects.get(product=product)
        with image.image.open('rb') as saved:
            data = saved.read()
        self.assertNotIn(marker, data)
        Image.open(io.BytesIO(data)).verify()

    def test_entire_upload_batch_is_validated_before_product_save(self):
        self.client.force_login(self.manager)
        bad = SimpleUploadedFile('page.html', b'<!doctype html><title>Test</title>', content_type='text/html')
        response = self.client.post('/add-product/', self.product_data([photo(), bad]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertFalse(Product.objects.filter(title='New tool').exists())
        self.assertEqual(list(Path(self.media.name).rglob('*')), [])

    def test_html_extension_is_rejected_even_with_valid_image_bytes(self):
        self.client.force_login(self.manager)
        response = self.client.post('/add-product/', self.product_data([photo(name='photo.html')]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(title='New tool').exists())

    def test_oversized_upload_is_rejected(self):
        self.client.force_login(self.manager)
        image = SimpleUploadedFile('large.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png')
        response = self.client.post('/add-product/', self.product_data([image]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(title='New tool').exists())

    def test_large_pixel_count_is_rejected_before_save(self):
        self.client.force_login(self.manager)
        response = self.client.post('/add-product/', self.product_data([photo(size=(4000, 4000))]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(title='New tool').exists())

    def review_data(self, images=()):
        return {'review_submit': '1', 'text': 'A useful tool', 'rating': '5', 'review_images': list(images)}

    def test_review_rejects_invalid_upload_without_saving_review(self):
        bad = SimpleUploadedFile('page.html', b'<title>Test</title>', content_type='text/html')
        response = self.client.post(f'/product/{self.product.pk}/', self.review_data([bad]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertFalse(Review.objects.exists())

    def test_review_rejects_more_than_five_photos(self):
        response = self.client.post(f'/product/{self.product.pk}/', self.review_data([photo() for _ in range(6)]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.exists())

    def test_anonymous_review_is_rejected(self):
        self.client.logout()
        response = self.client.post(f'/product/{self.product.pk}/', self.review_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_review_can_be_submitted_after_page_view(self):
        self.client.get(f'/product/{self.product.pk}/')
        response = self.client.post(f'/product/{self.product.pk}/', self.review_data([photo()]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.get().images.count(), 1)

    def test_cart_post_is_processed_after_page_view(self):
        self.client.get(f'/product/{self.product.pk}/')
        response = self.client.post(f'/product/{self.product.pk}/', {'add_to_cart': '1', 'quantity': '2'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(OrderItem.objects.get().quantity, 2)

    def test_quick_view_favorite_state_is_per_request(self):
        Favorite.objects.create(user=self.user, product=self.product)
        path = f'/api/product/{self.product.pk}/quick-view/'
        self.assertTrue(self.client.get(path).json()['is_favorited'])
        self.client.logout()
        self.assertFalse(self.client.get(path).json()['is_favorited'])

    def test_product_page_favorites_do_not_leak_to_anonymous_user(self):
        Favorite.objects.create(user=self.user, product=self.product)
        self.client.get(f'/product/{self.product.pk}/')
        self.client.logout()
        response = self.client.get(f'/product/{self.product.pk}/')
        self.assertEqual(response.context['favorite_product_ids'], [])

    def test_quick_view_price_changes_are_visible_immediately(self):
        path = f'/api/product/{self.product.pk}/quick-view/'
        self.client.get(path)
        self.product.price = '200.00'
        self.product.save()
        self.assertEqual(self.client.get(path).json()['price'], '200')

    def test_personalized_product_responses_disallow_shared_http_caches(self):
        for path in [f'/product/{self.product.pk}/', f'/api/product/{self.product.pk}/quick-view/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn('private', response.headers.get('Cache-Control', ''))
                self.assertIn('no-store', response.headers.get('Cache-Control', ''))


class RegistrationSecurityTests(TestCase):
    def form(self, password, email='new@example.invalid'):
        return ExtendedRegistrationForm({'first_name': 'Buyer', 'email': email,
            'password': password, 'password2': password, 'terms': True})

    def test_registration_rejects_short_common_and_numeric_passwords(self):
        for password in ['1', 'password', '1234567890']:
            with self.subTest(password=password):
                form = self.form(password)
                self.assertFalse(form.is_valid())
                self.assertIn('password', form.errors)

    def test_registration_accepts_strong_password(self):
        form = self.form('New-customer-9813!')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.check_password('New-customer-9813!'))

    def test_registration_rejects_existing_email_case_variant(self):
        User.objects.create_user('existing', email='Buyer@example.invalid')
        form = self.form('New-customer-9813!', 'buyer@EXAMPLE.invalid')
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

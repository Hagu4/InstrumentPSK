import pickle
from unittest.mock import patch
from django.core.cache import cache
from django.test import TestCase, override_settings
from .forms import ReviewForm
from .models import Product


class UnpickleableReviewForm(ReviewForm):
    def __reduce_ex__(self, protocol):
        raise pickle.PicklingError('Form cannot be serialized')


@override_settings(SECURE_SSL_REDIRECT=False)
class ProductCacheRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.product = Product.objects.create(title='Cache regression product', price='100.00', quantity=2)

    def test_unpickleable_form_does_not_break_product_page(self):
        with patch('app.views.ReviewForm', UnpickleableReviewForm):
            for _ in range(2):
                response = self.client.get(f'/product/{self.product.pk}/')
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Cache regression product')

    def test_obsolete_shared_context_is_not_used(self):
        cache.set(f'product_detail_{self.product.pk}', {'title': 'STALE_OTHER_USER_CONTEXT'})
        response = self.client.get(f'/product/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cache regression product')
        self.assertNotContains(response, 'STALE_OTHER_USER_CONTEXT')

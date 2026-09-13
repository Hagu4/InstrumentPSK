document.addEventListener('DOMContentLoaded', function() {
    console.log('quick-view.js: DOMContentLoaded event fired.');

    const modalOverlay = document.querySelector('.modal-overlay');
    const modalContent = document.querySelector('.modal-content');
    const modalCloseBtn = document.querySelector('.modal-close');
    const qvTriggerBtns = document.querySelectorAll('.quick-view-btn');
    
    if (!modalContent || !modalOverlay || !modalCloseBtn || qvTriggerBtns.length === 0) {
        console.log('quick-view.js: Modal components not found or no trigger buttons.');
        return; 
    }
    console.log('quick-view.js: Modal components and trigger buttons found.', qvTriggerBtns);

    const modalProductImage = modalContent.querySelector('.modal-product-image');
    const modalImgNav = modalContent.querySelector('.modal-img-nav'); // New: Image navigation container
    const modalBrand = modalContent.querySelector('.modal-brand');
    const modalName = modalContent.querySelector('.modal-name');
    const modalRating = modalContent.querySelector('.modal-rating');
    const reviewsCount = modalRating.querySelector('.reviews-count');
    const modalSpecsGrid = modalContent.querySelector('.modal-specs-grid');
    const modalCurrentPrice = modalContent.querySelector('.modal-current-price');
    const modalOldPrice = modalContent.querySelector('.modal-old-price');
    const modalDiscountPercent = modalContent.querySelector('.modal-discount-percent');
    const modalAddBtn = modalContent.querySelector('.modal-add-btn');
    const modalFavoriteBtn = modalContent.querySelector('.modal-favorite-btn');
    const modalDesc = modalContent.querySelector('.modal-desc');

    let currentImageIndex = 0; // To keep track of the active image

    function openModal() {
        console.log('quick-view.js: openModal() called.');
        modalOverlay.classList.add('active');
        modalContent.classList.add('active');
    }

    function closeModal() {
        console.log('quick-view.js: closeModal() called.');
        modalOverlay.classList.remove('active');
        modalContent.classList.remove('active');
        currentImageIndex = 0; // Reset image index on close
    }

    function showLoading() {
        modalProductImage.src = '';
        modalBrand.textContent = '';
        modalName.textContent = 'Загрузка...';
        modalRating.innerHTML = '';
        reviewsCount.textContent = '';
        modalDesc.textContent = '';
        modalSpecsGrid.innerHTML = '';
        modalOldPrice.style.display = 'none';
        modalDiscountPercent.style.display = 'none';
        modalCurrentPrice.textContent = '... ₽';
        modalAddBtn.textContent = 'Добавить';
        modalAddBtn.disabled = true;
        modalFavoriteBtn.disabled = true;
        modalFavoriteBtn.classList.remove('favorited');
        modalImgNav.innerHTML = ''; // Clear image dots
        modalImgNav.style.display = 'none'; // Hide image dots container
    }

    function hideLoadingAndShowContent(data) {
        console.log('quick-view.js: hideLoadingAndShowContent() called with data:', data);
        
        // Image Gallery Logic
        if (data.images && data.images.length > 1) {
            modalImgNav.innerHTML = ''; // Clear previous dots
            modalImgNav.style.display = 'flex'; // Show image dots container
            data.images.forEach((image, index) => {
                const dot = document.createElement('div');
                dot.classList.add('modal-img-dot');
                dot.dataset.imageUrl = image.url;
                dot.dataset.index = index;
                if (index === currentImageIndex) {
                    dot.classList.add('active');
                }
                dot.addEventListener('click', function() {
                    modalProductImage.src = this.dataset.imageUrl;
                    currentImageIndex = parseInt(this.dataset.index);
                    // Remove active class from all dots
                    modalImgNav.querySelectorAll('.modal-img-dot').forEach(d => d.classList.remove('active'));
                    // Add active class to clicked dot
                    this.classList.add('active');
                });
                modalImgNav.appendChild(dot);
            });
            modalProductImage.src = data.images[currentImageIndex].url; // Set initial image
        } else {
            modalProductImage.src = data.image_url || '/static/app/content/no_image.png'; // Corrected fallback path
            modalImgNav.innerHTML = '';
            modalImgNav.style.display = 'none';
        }
        modalProductImage.alt = data.title;
        
        if (modalBrand) {
            modalBrand.textContent = data.brand;
            modalBrand.href = data.brand_url;
        }
        if (modalName) {
            modalName.textContent = data.title;
        }
        // if (modalDesc) { // Populate description - removed to prevent duplication
        //     modalDesc.textContent = data.specs_line;
        // }
        
        modalSpecsGrid.innerHTML = '';
        if (data.features && data.features.length > 0) {
            data.features.forEach(feature => {
                const specDiv = document.createElement('div');
                specDiv.classList.add('modal-spec');
                const label = document.createElement('div');
                label.className = 'modal-spec-label';
                label.textContent = feature.name;
                const value = document.createElement('div');
                value.className = 'modal-spec-value';
                value.textContent = feature.value;
                specDiv.append(label, value);
                modalSpecsGrid.appendChild(specDiv);
            });
        }

        // Set URLs for the new links
        const modalAllSpecsLink = document.querySelector('.modal-all-specs-link');
        const modalViewProductBtn = document.querySelector('.modal-view-product-btn');
        
        if (modalAllSpecsLink) {
            modalAllSpecsLink.href = data.detail_url + '#specs';
        }
        if (modalViewProductBtn) {
            modalViewProductBtn.href = data.detail_url;
        }

        // Price and Discount Logic
        const setPrice = (element, price) => {
            const currency = document.createElement('span');
            currency.className = 'currency';
            currency.textContent = '₽';
            element.replaceChildren(document.createTextNode(`${price} `), currency);
        };
        setPrice(modalCurrentPrice, data.price);
        if (data.old_price && parseFloat(data.old_price) > parseFloat(data.price)) {
            const discount = ((parseFloat(data.old_price) - parseFloat(data.price)) / parseFloat(data.old_price)) * 100;
            setPrice(modalOldPrice, data.old_price);
            modalOldPrice.style.display = 'inline-flex';
            modalDiscountPercent.textContent = `-${discount.toFixed(0)}%`;
            modalDiscountPercent.style.display = 'inline-block';
        } else {
            modalOldPrice.style.display = 'none';
            modalDiscountPercent.style.display = 'none';
        }

        // Populate rating
        if (modalRating) {
            modalRating.innerHTML = '';
            if (data.review_count > 0) {
                const avgRating = data.average_rating || 0;
                for (let i = 0; i < 5; i++) {
                    const starSvg = `<svg class="star-icon ${i < avgRating ? 'filled' : 'empty'}" viewBox="0 0 24 24"><path d="M12 .587l3.668 7.431 8.216 1.191-5.945 5.795 1.403 8.175L12 18.896l-7.342 3.868 1.403-8.175L.116 9.209l8.216-1.191L12 .587z"/></svg>`;
                    modalRating.insertAdjacentHTML('beforeend', starSvg);
                }
                const reviewsSpan = document.createElement('span');
                reviewsSpan.classList.add('reviews-count');
                reviewsSpan.textContent = `(${data.review_count})`;
                modalRating.appendChild(reviewsSpan);
            } else {
                const noReviewsSpan = document.createElement('span');
                noReviewsSpan.classList.add('reviews-count');
                noReviewsSpan.textContent = '(Нет отзывов)';
                modalRating.appendChild(noReviewsSpan);
            }
        }

        // Update add to cart button
        if (modalAddBtn) {
            modalAddBtn.dataset.productId = data.id;
            modalAddBtn.disabled = !data.in_stock;
            if (!data.in_stock) {
                modalAddBtn.textContent = 'Нет в наличии';
                modalAddBtn.classList.add('disabled');
            } else {
                modalAddBtn.textContent = 'В корзину';
                modalAddBtn.classList.remove('disabled');
            }
        }

        // Update favorite button
        if (modalFavoriteBtn) {
            modalFavoriteBtn.dataset.productId = data.id;
            if (data.is_favorited) {
                modalFavoriteBtn.classList.add('is-favorite');
            } else {
                modalFavoriteBtn.classList.remove('is-favorite');
            }
            modalFavoriteBtn.disabled = false;
        }
    }

    qvTriggerBtns.forEach(btn => {
        btn.addEventListener('click', function(event) {
            console.log('quick-view.js: Quick view button clicked!');
            event.preventDefault();
            const productId = this.dataset.productId;
            console.log('quick-view.js: Product ID:', productId);
            if (!productId) {
                console.error('quick-view.js: Product ID not found on button.');
                return;
            }
            
            showLoading();
            openModal();

            fetch(`/api/product/${productId}/quick-view/`)
                .then(response => {
                    console.log('quick-view.js: Fetch response received:', response);
                    if (!response.ok) {
                        if(response.status === 403 || response.status === 401) {
                             window.location.href = window.loginUrl + '?next=' + window.location.pathname;
                        }
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('quick-view.js: Fetch data received:', data);
                    hideLoadingAndShowContent(data);
                })
                .catch(error => {
                    console.error('quick-view.js: Error fetching quick view data:', error);
                    alert('Не удалось загрузить данные о товаре.');
                    closeModal();
                });
        });
    });

    // Add to cart from modal
    if (modalAddBtn) {
        modalAddBtn.addEventListener('click', function() {
            console.log('quick-view.js: Add to cart button in modal clicked!');
            const productId = this.dataset.productId;
            const productTitle = modalName.textContent;

            fetch('/ajax/add-to-cart/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({ product_id: productId, quantity: 1 })
            })
            .then(response => {
                console.log('quick-view.js: Add to cart fetch response received:', response);
                if (!response.ok) {
                    if(response.status === 403 || response.status === 401) {
                         window.location.href = window.loginUrl + '?next=' + window.location.pathname;
                    }
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log('quick-view.js: Add to cart fetch data received:', data);
                if (data.status === 'success') {
                    const cartBadge = document.getElementById('cart-badge');
                    if (cartBadge) {
                        const newCount = data.total_items;
                        cartBadge.textContent = newCount;
                        if (newCount > 0) {
                            cartBadge.style.display = 'flex';
                            cartBadge.classList.remove('pulse');
                            void cartBadge.offsetWidth;
                            cartBadge.classList.add('pulse');
                        } else {
                            cartBadge.style.display = 'none';
                            cartBadge.classList.remove('pulse');
                        }
                    }
                    window.showToast(data.message, 'success', productTitle);
                    closeModal();
                } else {
                    window.showToast(data.message || 'Не удалось добавить товар', 'error');
                }
            })
            .catch(error => {
                console.error('quick-view.js: Error adding to cart:', error);
                window.showToast('Произошла ошибка при добавлении товара в корзину.', 'error');
            });
        });
    }

    // Favorite button logic
    if (modalFavoriteBtn) {
        modalFavoriteBtn.addEventListener('click', function() {
            console.log('quick-view.js: Favorite button clicked!');
            const productId = this.dataset.productId;
            if (!productId) {
                console.error('quick-view.js: Product ID not found on favorite button.');
                return;
            }

            fetch(`/product/${productId}/toggle_favorite/`, { // Corrected endpoint for favorite
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({ product_id: productId })
            })
            .then(response => {
                if (!response.ok) {
                    if(response.status === 403 || response.status === 401) {
                         window.location.href = window.loginUrl + '?next=' + window.location.pathname;
                    }
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    if (data.is_favorited) {
                        modalFavoriteBtn.classList.add('is-favorite');
                        window.showToast('Товар добавлен в избранное!', 'success');
                    } else {
                        modalFavoriteBtn.classList.remove('is-favorite');
                        window.showToast('Товар удален из избранного!', 'info');
                    }

                    // --- NEW LOGIC FOR SYNCHRONIZATION ---
                    // Find all favorite buttons on the page with the same product ID
                    const allFavoriteButtons = document.querySelectorAll(`.favorite-btn[data-product-id="${productId}"]`);
                    allFavoriteButtons.forEach(btn => {
                        if (data.is_favorited) {
                            btn.classList.add('is-favorite');
                        } else {
                            btn.classList.remove('is-favorite');
                        }
                    });
                    // --- END NEW LOGIC ---

                } else {
                    window.showToast(data.message || 'Не удалось изменить статус избранного.', 'error');
                }
            })
            .catch(error => {
                console.error('quick-view.js: Error toggling favorite:', error);
                window.showToast('Произошла ошибка при изменении статуса избранного.', 'error');
            });
        });
    }


    modalCloseBtn.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', function(event) {
        if (event.target === modalOverlay) {
            closeModal();
        }
    });
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modalOverlay.classList.contains('active')) {
            closeModal();
        }
    });
});

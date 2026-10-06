document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements (Robust Selection) ---
    const searchContainer = document.querySelector('form.search-container');
    
    // Stop if the main container isn't found
    if (!searchContainer) {
        console.warn('Live Search Aborted: Main search container (`form.search-container`) not found.');
        return;
    }

    const searchInput = searchContainer.querySelector('#search-input');
    const searchResults = searchContainer.querySelector('#search-results');
    const spinner = searchContainer.querySelector('.spinner');
    
    // Stop if any of the essential inner elements are missing
    if (!searchInput || !searchResults || !spinner) {
        console.warn('Live Search Aborted: One or more required elements (#search-input, #search-results, .spinner) not found inside the container.');
        return;
    }
    
    const searchUrl = searchContainer.dataset.searchUrl;
    if (!searchUrl) {
        console.error('Live Search Aborted: Search URL is not provided in `data-search-url` attribute.');
        return;
    }
    console.log('Live search script initialized. Search URL:', searchUrl);

    // --- Debounce Function ---
    function debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // --- Search Logic ---
    const handleSearch = async (query) => {
        console.log('handleSearch called with query:', query);
        if (!query.trim()) {
            spinner.style.display = 'none';
            searchResults.style.display = 'none';
            console.log('Query is empty, hiding results.');
            return;
        }
        
        spinner.style.display = 'block';
        console.log('Fetching search results for:', query);

        try {
            const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`);
            console.log('Fetch response received:', response);
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Network response was not ok: ${response.status} ${response.statusText} - ${errorText}`);
            }
            const data = await response.json();
            console.log('Data received from API:', data);
            renderResults(data);
        } catch (error) {
            console.error('Error fetching search results:', error);
            searchResults.innerHTML = '<div class="no-results" style="padding: 2rem; text-align: center;"><i class="fas fa-exclamation-triangle" style="font-size: 2rem; color: #ffc107; margin-bottom: 0.5rem; display: block;"></i><div style="color: #6c757d;">Ошибка поиска</div><div style="color: #999; font-size: 0.85rem; margin-top: 0.25rem;">Попробуйте позже</div></div>';
            searchResults.style.display = 'block';
        } finally {
            spinner.style.display = 'none';
        }
    };

    // --- Render Results ---
    function renderResults(data) {
        console.log('renderResults called with data:', data);
        searchResults.innerHTML = ''; // Clear previous results

        if (data.length === 0) {
            searchResults.innerHTML = '<div class="no-results" style="padding: 2rem; text-align: center;"><i class="fas fa-search" style="font-size: 2rem; color: #ccc; margin-bottom: 0.5rem; display: block;"></i><div style="color: #6c757d;">Ничего не найдено</div><div style="color: #999; font-size: 0.85rem; margin-top: 0.25rem;">Попробуйте изменить запрос</div></div>';
            console.log('No results found.');
        } else {
            data.forEach(item => {
                const itemElement = document.createElement('a');
                itemElement.className = 'search-results-item';
                itemElement.href = item.url;
                
                const textElement = (tag, className, text) => {
                    const element = document.createElement(tag);
                    element.className = className;
                    element.textContent = text ?? '';
                    return element;
                };
                const picture = document.createElement(item.image_url ? 'img' : 'div');
                picture.className = item.image_url ? 'item-image' : 'item-image placeholder';
                if (item.image_url) {
                    picture.src = item.image_url;
                    picture.alt = item.name ?? '';
                }
                const details = textElement('div', 'item-details', '');
                details.append(textElement('span', 'item-name', item.name),
                    textElement('span', 'item-category', item.category));
                if (item.matched_chars?.length) {
                    details.append(textElement('div', 'item-matched-chars', item.matched_chars.join(', ')));
                }
                const meta = textElement('div', 'item-meta', '');
                meta.append(textElement('span', 'item-brand', item.brand),
                    textElement('span', 'item-sku', `Арт: ${item.sku ?? ''}`));
                details.append(meta);
                itemElement.append(picture, details);
                searchResults.appendChild(itemElement);
            });
        }
        
        searchResults.style.display = 'block';
    }

    // --- Event Listeners ---
    const debouncedSearch = debounce(handleSearch, 300);

    searchInput.addEventListener('input', (e) => {
        debouncedSearch(e.target.value);
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchContainer.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });
});

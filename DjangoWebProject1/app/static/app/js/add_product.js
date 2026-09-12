// D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\static\app\js\add_product.js

document.addEventListener('DOMContentLoaded', function() {
    
    // --- Advanced Multi-Image Handler ---
    const form = document.querySelector('.form-card form');
    const imageInput = document.getElementById('id_images');
    const previewsContainer = document.getElementById('previews-container');
    const uploadZone = document.querySelector('.upload-zone');
    
    // This buffer will hold our files
    let fileBuffer = [];

    const updatePreviews = () => {
        previewsContainer.innerHTML = ''; // Clear previews
        
        // Create a new FileList for the input
        const dataTransfer = new DataTransfer();

        fileBuffer.forEach((file, index) => {
            // Add to the DataTransfer
            dataTransfer.items.add(file);

            // Create preview element
            const previewItem = document.createElement('div');
            previewItem.className = 'preview-item';
            
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file); // Use URL.createObjectURL for performance
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'preview-remove-btn';
            removeBtn.innerHTML = '×';
            removeBtn.type = 'button'; // Prevent form submission

            removeBtn.addEventListener('click', () => {
                fileBuffer.splice(index, 1); // Remove file from buffer
                updatePreviews(); // Re-render
            });

            previewItem.appendChild(img);
            previewItem.appendChild(removeBtn);
            previewsContainer.appendChild(previewItem);
        });

        // Update the actual input's FileList
        imageInput.files = dataTransfer.files;
    };

    const addFilesToBuffer = (files) => {
        const newFiles = Array.from(files);
        // You could add duplicate-checking here if needed
        fileBuffer.push(...newFiles);
        updatePreviews();
    };

    if (form && imageInput && previewsContainer && uploadZone) {
        // Listener for file selection via click
        imageInput.addEventListener('change', (event) => {
            addFilesToBuffer(event.target.files);
        });

        // Listeners for Drag & Drop
        uploadZone.addEventListener('dragover', (event) => {
            event.preventDefault();
            uploadZone.classList.add('drag-over');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('drag-over');
        });

        uploadZone.addEventListener('drop', (event) => {
            event.preventDefault();
            uploadZone.classList.remove('drag-over');
            addFilesToBuffer(event.dataTransfer.files);
        });

        // No need to hijack the form submission anymore,
        // because we are now successfully updating imageInput.files
        // The browser will handle the FormData construction on its own.
    }


    // --- Characteristics Repeater (No changes needed here) ---
    const characteristicsList = document.getElementById('characteristics-list');
    const addCharacteristicBtn = document.getElementById('add-characteristic-btn');
    const emptyFormTemplate = document.getElementById('empty-form-template');
    const totalFormsInput = document.querySelector('[name="characteristics-TOTAL_FORMS"]');

    if (addCharacteristicBtn) {
        addCharacteristicBtn.addEventListener('click', function() {
            if (!totalFormsInput || !emptyFormTemplate) return;
            
            let formNum = parseInt(totalFormsInput.value);
            
            let tempDiv = document.createElement('div');
            tempDiv.innerHTML = emptyFormTemplate.innerHTML.replace(/__prefix__/g, formNum);
            const newFormElement = tempDiv.firstElementChild; // This is the .char-row

            if (characteristicsList) {
                characteristicsList.appendChild(newFormElement);
            }

            totalFormsInput.value = formNum + 1;

            attachRemoveListener(newFormElement);
        });
    }

    function attachRemoveListener(rowElement) {
        const removeBtn = rowElement.querySelector('.remove-btn');
        if (removeBtn) {
            removeBtn.addEventListener('click', function() {
                const deleteCheckbox = rowElement.querySelector('input[type="checkbox"][id$="-DELETE"]');
                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                    rowElement.style.display = 'none';
                } else {
                    rowElement.remove();
                }
            });
        }
    }

    if (characteristicsList) {
        characteristicsList.querySelectorAll('.char-row').forEach(function(row) {
            attachRemoveListener(row);
        });
    }
});

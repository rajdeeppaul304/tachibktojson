function loadScanlators() {
    const mangaTitle = document.getElementById('mangaSelect').value;
    
    if (!mangaTitle) return;
    
    fetch('/get_scanlators', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ manga_title: mangaTitle })
    })
    .then(response => response.json())
    .then(data => {
        const scanlatorsContainer = document.getElementById('scanlatorsContainer');
        scanlatorsContainer.innerHTML = '';

        if (data.error) {
            scanlatorsContainer.innerHTML = `<p>${data.error}</p>`;
            document.getElementById('scanlatorsSection').style.display = 'block';
            return;
        }

        data.scanlators.forEach((scanlator, index) => {
            const label = document.createElement('label');
            label.textContent = scanlator;
            const select = document.createElement('select');
            select.id = `scanlator-${index}`;
            select.innerHTML = `
                <option value="">Select preference</option>
                ${[...Array(data.scanlators.length).keys()].map(i => `<option value="${i + 1}">${i + 1}</option>`).join('')}
            `;
            
            scanlatorsContainer.appendChild(label);
            scanlatorsContainer.appendChild(select);
            scanlatorsContainer.appendChild(document.createElement('br'));
        });

        document.getElementById('scanlatorsSection').style.display = 'block';
    })
    .catch(error => console.error('Error:', error));
}

function updatePreferences() {
    const mangaTitle = document.getElementById('mangaSelect').value;
    const preferences = Array.from(document.querySelectorAll('select[id^="scanlator-"]')).reduce((prefs, select) => {
        const scanlator = select.previousSibling.textContent.trim();
        const preference = select.value;
        if (preference) {
            prefs[scanlator] = preference;
        }
        return prefs;
    }, {});

    fetch('/update_preferences', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ manga_title: mangaTitle, preferences: preferences })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Updated data:', data);
        alert('Preferences updated successfully.');
    })
    .catch(error => console.error('Error:', error));
}




function deletion_duplicates() {
    const mangaTitle = document.getElementById('mangaSelect2').value;


    fetch('/delete_duplicates', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ manga_title: mangaTitle})
    })
    .then(response => response.json())
    .then(data => {
        console.log('Updated data:', data);
        alert('manga_title duplicate deleted successfully.');
    })
    .catch(error => console.error('Error:', error));
}



document.getElementById('uploadForm').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent default form submission

    const formData = new FormData();
    const fileInput = document.getElementById('fileInput');
    
    if (fileInput.files.length === 0) {
        document.getElementById('message').textContent = 'Please select a file to upload.';
        return;
    }
    
    formData.append('file', fileInput.files[0]);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            document.getElementById('message').textContent = `Error: ${data.error}`;
            document.getElementById('message').style.color = 'red';
        } else {
            document.getElementById('message').textContent = `Success: ${data.message}`;
            document.getElementById('message').style.color = 'green';
            document.getElementById('message').innerHTML += `<br>File path: ${data.file_path}`;
        }
    })
    .catch(error => {
        document.getElementById('message').textContent = `Error: ${error.message}`;
        document.getElementById('message').style.color = 'red';
    });
});



function processFile() {
    fetch('/parse_to_json', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        // Display the result
        const resultDiv = document.getElementById('result');
        if (data.error) {
            resultDiv.textContent = `Error: ${data.error}`;
        } else {
            resultDiv.textContent = `Message: ${data.message}\nFile Path: ${data.file_path}`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function processFile2() {
    fetch('/parse_to_tachibk', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        // Display the result
        const resultDiv = document.getElementById('result');
        if (data.error) {
            resultDiv.textContent = `Error: ${data.error}`;
        } else {
            resultDiv.textContent = `Message: ${data.message}\nFile Path: ${data.file_path}`;
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}





function uploadBlob() {
    const fileInput = document.getElementById('fileInput');
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = ''; // Clear any existing message

    if (fileInput.files.length === 0) {
        messageDiv.textContent = 'Please select a file!';
        messageDiv.style.color = 'red';
        return;
    }

    const file = fileInput.files[0];
    const reader = new FileReader();

    reader.onload = function(event) {
        const fileData = event.target.result;
        const blob = new Blob([fileData], { type: file.type });

        // Create FormData and append the Blob
        const formData = new FormData();
        formData.append('file', blob, 'backup.tachibk'); // Name is set as 'backup.tachibk'

        // Send the request
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                messageDiv.textContent = `Error: ${data.error}`;
                messageDiv.style.color = 'red';
            } else {
                messageDiv.textContent = `Success: ${data.message}`;
                messageDiv.style.color = 'green';
            }
        })
        .catch((error) => {
            messageDiv.textContent = `Error: ${error.message}`;
            messageDiv.style.color = 'red';
        });
    };

    reader.readAsArrayBuffer(file);
}

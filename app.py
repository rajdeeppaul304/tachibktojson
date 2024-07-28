from flask import Flask, request,send_file, jsonify, render_template
import json
import os
import subprocess

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'tachibk'}
app.config['BACKUP_FILENAME'] = 'backup.tachibk'


# Load the JSON file
with open('data.json') as f:
    data = json.load(f)
    
def load_data():
    with open('data.json', 'r') as file:
        return json.load(file)

# Save data to data.json
def save_data(data):
    with open('data.json', 'w') as file:
        json.dump(data, file, indent=4)

@app.route('/')
def index():
    manga_titles = [manga['title'] for manga in data['backupManga']]
    return render_template('index.html', manga_titles=manga_titles)

@app.route('/get_scanlators', methods=['POST'])
def get_scanlators():
    manga_title = request.json.get('manga_title')
    selected_manga = next((manga for manga in data['backupManga'] if manga['title'] == manga_title), None)

    if not selected_manga:
        return jsonify({'error': 'Manga not found'}), 404

    scanlators = set()
    for chapter in selected_manga['chapters']:
        scanlator = chapter.get('scanlator')
        if scanlator is None:
            pass
        else:
            scanlators.add(scanlator)
    print(scanlators)
    if len(scanlators)  == 0:
        return jsonify({'error': f"scanlators not available for [{manga_title}], use delete duplicate"})
    return jsonify({'scanlators': list(scanlators)})


@app.route('/update_preferences', methods=['POST'])
def update_preferences():
    manga_title = request.json.get('manga_title')
    preferences = request.json.get('preferences', {})
    
    # Load the current data from the file
    data = load_data()
    
    selected_manga = next((manga for manga in data['backupManga'] if manga['title'] == manga_title), None)

    if not selected_manga:
        return jsonify({'error': 'Manga not found'}), 404

    # Create scanlator preference mapping
    scanlator_preferences = {scanlator: idx + 1 for idx, scanlator in enumerate(preferences)}

    # Filter chapters based on scanlator preferences
    filtered_chapters = {}
    for chapter in selected_manga['chapters']:
        chapter_name = chapter['name']
        if chapter_name not in filtered_chapters:
            filtered_chapters[chapter_name] = chapter
        else:
            current_entry = filtered_chapters[chapter_name]
            current_pref = scanlator_preferences.get(current_entry['scanlator'], float('inf'))
            new_pref = scanlator_preferences.get(chapter['scanlator'], float('inf'))
            if new_pref < current_pref:
                filtered_chapters[chapter_name] = chapter

    selected_manga['chapters'] = list(filtered_chapters.values())

    # Save the updated data back to the file
    save_data(data)
    
    return jsonify({'message': 'Preferences updated successfully.'})



@app.route('/delete_duplicates', methods=['POST'])
def delete_duplicates():
    manga_title = request.json.get('manga_title')
    
    # Load the current data from the file
    data = load_data()
    
    selected_manga = next((manga for manga in data['backupManga'] if manga['title'] == manga_title), None)

    if not selected_manga:
        return jsonify({'error': 'Manga not found'}), 404

    # Find and delete duplicate chapters
    chapter_seen = set()
    unique_chapters = []

    for chapter in selected_manga['chapters']:
        chapter_key = (chapter['chapterNumber'])
        if chapter_key not in chapter_seen:
            chapter_seen.add(chapter_key)
            unique_chapters.append(chapter)

    selected_manga['chapters'] = unique_chapters

    # Save the updated data back to the file
    save_data(data)
    
    return jsonify({'message': 'Duplicate chapters deleted successfully.'})





app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    # Create the file path
    file_path = os.path.join("downloadable", filename)
    
    # Check if the file exists
    if not os.path.isfile(file_path):
        return jsonify({'error': 'File not found'}), 404

    # Send the file for download
    return send_file(file_path, as_attachment=True)



@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        # Save the file data to the specific backup file
        backup_file_path = os.path.join(app.config['UPLOAD_FOLDER'], app.config['BACKUP_FILENAME'])
        
        # Open the file in write binary mode and save the content
        with open(backup_file_path, 'wb') as backup_file:
            backup_file.write(file.read())
        
        return jsonify({'message': 'File successfully updated', 'file_path': backup_file_path}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_command(input_path, output_path):
    command = ["python", "tachibk_converter.py", "--input", input_path, "--output", output_path]
    
    try:
        # Run the command
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # Print stdout and stderr
        print("Standard Output:", result.stdout)
        print("Standard Error:", result.stderr)
        
        return {'success': True, 'message': 'Command executed successfully'}
        
    except subprocess.CalledProcessError as e:
        error_message = f"Error occurred while running the command: {e}\nReturn code: {e.returncode}\nOutput: {e.output}\nError Output: {e.stderr}"
        print(error_message)
        return {'success': False, 'error': error_message}
        
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(error_message)
        return {'success': False, 'error': error_message}


@app.route('/parse_to_json', methods=['POST'])
def parse_to_json():
    try:
        # Ensure there is a file in the uploads folder
        files = os.listdir("uploads")
        if not files:
            return jsonify({'success': False, 'error': 'No file found in the uploads folder'}), 400

        file_path = os.path.join("uploads", files[0])
        result = run_command(file_path, "data.json")
        
        # Return the result of the command execution
        if result['success']:
            return jsonify({'message': 'File successfully parsed from tachibk to JSON', 'file_path': file_path})
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/parse_to_tachibk', methods=['POST'])
def parse_to_tachibk():
    try:
        # Ensure there is a file in the uploads folder
        files = os.listdir("uploads")
        if not files:
            return jsonify({'success': False, 'error': 'No file found in the uploads folder'}), 400

        file_path = os.path.join("downloadable", files[0])

        existing_files = os.listdir("downloadable")
        if existing_files:
            existing_file_path = os.path.join("downloadable", existing_files[0])
            os.remove(existing_file_path)

        
        result = run_command("data.json", file_path)
        
        # Return the result of the command execution
        if result['success']:
            return jsonify({'message': 'File successfully parsed from JSON to tachibk', 'file_path': file_path})
        else:
            return jsonify({'error': result['error']}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    app.run()
# # waitress-serve --host=192.168.144.1 --port=8080 main:app
import os, subprocess, platform, signal, asyncio, stat
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from werkzeug.utils import secure_filename

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "sessions")
ALLOWED_EXTENSIONS = set(['session'])
MAX_CONTENT_LENGTH = 100 * 1024 * 1024 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

flask_process = None
tunnel_process = None

def allowed_file(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File is too large. Maximum size: 100MB'}), 413

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/', methods=['GET'])
def index():
    return render_template_string('''
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <title>Session Manager by @mffff4</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/dropzone/5.9.3/min/dropzone.min.css" rel="stylesheet"/>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"/>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
        <style>
          .dropzone { border: 2px dashed #6366F1; border-radius: 12px; background-color: #E5E7EB; min-height: 150px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
          .dz-message { font-weight: 500; font-size: 1.25rem; color: #4F46E5; text-align: center; }
          .dropzone:hover { background-color: #D1D5DB; }
          .file-list th, .file-list td { vertical-align: middle; }
          @media (max-width: 768px) { .file-list th, .file-list td { padding: 0.5rem; } }
        </style>
      </head>
      <body class="bg-gradient-to-r from-indigo-500 to-purple-600 min-h-screen flex items-center justify-center p-4">
        <div class="w-full max-w-4xl p-6 bg-white rounded-xl shadow-lg animate__animated animate__fadeInUp">
          <h1 class="text-3xl font-semibold text-center text-gray-800 mb-6">Session Manager by @mffff4</h1>
          <div class="mb-6">
            <form action="/upload" class="dropzone" id="upload-dropzone">
              <div class="dz-message">Drag & drop files here or click to upload<br/><span class="text-sm text-gray-500">(Max file size: 100MB)</span></div>
            </form>
            <div id="upload-status" class="mt-4"></div>
          </div>
          <div>
            <h2 class="text-2xl font-semibold text-gray-700 mb-4">Files</h2>
            <div class="overflow-x-auto">
              <table class="min-w-full bg-white file-list">
                <thead>
                  <tr>
                    <th class="py-2 px-4 border-b">#</th>
                    <th class="py-2 px-4 border-b">Filename</th>
                    <th class="py-2 px-4 border-b">Actions</th>
                  </tr>
                </thead>
                <tbody id="file-table-body"></tbody>
              </table>
            </div>
            <div id="file-status" class="mt-4"></div>
          </div>
        </div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/dropzone/5.9.3/min/dropzone.min.js"></script>
        <script>
          Dropzone.autoDiscover = false;
          const uploadDropzone = new Dropzone("#upload-dropzone", { 
            paramName: "file", 
            maxFilesize: 100, 
            acceptedFiles: ".session", 
            addRemoveLinks: false,
            dictDefaultMessage: "Drag & drop files here or click to upload",
            init: function() {
              this.on("success", function(file, response) {
                displayStatus('upload-status', 'success', response.success);
                this.removeFile(file);
                loadFiles();
              });
              this.on("error", function(file, response) {
                let errorMsg = typeof response === 'string' ? response : (response.error || 'An error occurred during upload.');
                displayStatus('upload-status', 'error', errorMsg);
                this.removeFile(file);
              });
            }
          });

          function displayStatus(elementId, type, message) {
            const statusDiv = document.getElementById(elementId);
            let bgColor = type === 'success' ? 'bg-green-100' : 'bg-red-100';
            let textColor = type === 'success' ? 'text-green-700' : 'text-red-700';
            statusDiv.innerHTML = `<div class="${bgColor} ${textColor} border px-4 py-3 rounded relative"><span class="block sm:inline">${message}</span></div>`;
            setTimeout(() => { statusDiv.innerHTML = ''; }, 5000);
          }

          function loadFiles() {
            fetch('/files')
              .then(response => response.json())
              .then(data => {
                const tableBody = document.getElementById('file-table-body');
                tableBody.innerHTML = '';
                if (data.files.length === 0) {
                  tableBody.innerHTML = `<tr><td colspan="3" class="py-2 px-4 border-b text-center text-gray-500">No files found.</td></tr>`;
                  return;
                }
                data.files.forEach((file, index) => {
                  tableBody.innerHTML += `
                    <tr>
                      <td class="py-2 px-4 border-b text-center">${index + 1}</td>
                      <td class="py-2 px-4 border-b text-gray-700">${file}</td>
                      <td class="py-2 px-4 border-b text-center">
                        <button onclick="downloadFile('${encodeURIComponent(file)}')" class="text-blue-500 hover:text-blue-700 mr-2"><i class="fas fa-download"></i></button>
                        <button onclick="renameFilePrompt('${encodeURIComponent(file)}')" class="text-yellow-500 hover:text-yellow-700 mr-2"><i class="fas fa-pen"></i></button>
                        <button onclick="deleteFile('${encodeURIComponent(file)}')" class="text-red-500 hover:text-red-700"><i class="fas fa-trash"></i></button>
                      </td>
                    </tr>`;
                });
              })
              .catch(error => displayStatus('file-status', 'error', 'Failed to load files.'));
          }

          function deleteFile(filename) {
            if (!confirm(`Are you sure you want to delete "${decodeURIComponent(filename)}"?`)) return;
            fetch(`/delete/${filename}`, {
              method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
              if (data.success) {
                displayStatus('file-status', 'success', data.success);
                loadFiles();
              } else {
                displayStatus('file-status', 'error', data.error);
              }
            })
            .catch(error => displayStatus('file-status', 'error', 'Failed to delete file.'));
          }

          function renameFilePrompt(oldName) {
            const oldNameWithoutExt = oldName.replace('.session', '');
            const newName = prompt("Enter new name for the file:", oldNameWithoutExt);
            if (newName && newName.trim() !== "" && newName !== oldNameWithoutExt) {
                fetch('/rename', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ old_name: oldName, new_name: newName })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displayStatus('file-status', 'success', data.success);
                        loadFiles();
                    } else {
                        displayStatus('file-status', 'error', data.error);
                    }
                })
                .catch(error => displayStatus('file-status', 'error', 'Failed to rename file.'));
            }
          }

          function downloadFile(filename) {
            window.location.href = `/download/${filename}`;
          }

          document.addEventListener('DOMContentLoaded', () => {
            loadFiles();
          });

          document.addEventListener('dragover', function(event) {
            event.preventDefault();
            event.stopPropagation();
          }, false);

          document.addEventListener('drop', function(event) {
            event.preventDefault();
            event.stopPropagation();
          }, false);
        </script>
      </body>
    </html>
    ''')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("Received file upload request")
    if 'file' not in request.files:
        error_msg = 'No file in the request'
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg}), 400
    file = request.files['file']
    print(f"Uploaded file name: {file.filename}")
    if file.filename == '':
        error_msg = 'No file selected'
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg}), 400
    if file and allowed_file(file.filename):
        filename = file.filename
        print(f"Processed file name: {filename}")
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(f"File save path: {save_path}")
        try:
            file.save(save_path)
            success_msg = f"File '{filename}' successfully uploaded"
            print(success_msg)
            return jsonify({'success': success_msg}), 200
        except Exception as e:
            error_msg = f"Failed to save file: {str(e)}"
            print(f"Error: {error_msg}")
            return jsonify({'error': error_msg}), 500
    else:
        error_msg = 'File type not allowed'
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg}), 400

def get_file_name_without_extension(filename):
    return os.path.splitext(filename)[0]

@app.route('/files', methods=['GET'])
def list_files():
    try:
        all_files = os.listdir(UPLOAD_FOLDER)
        files = [f for f in all_files if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and f.endswith('.session')]
        return jsonify({'files': files}), 200
    except Exception as e:
        error_msg = f'Failed to get file list: {str(e)}'
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/rename', methods=['POST'])
def rename_file():
    try:
        data = request.get_json()
        old_name = data.get('old_name', '')
        new_name = data.get('new_name', '')
        
        if not old_name or not new_name:
            return jsonify({'error': 'Invalid file names'}), 400

        if not old_name.endswith('.session'):
            old_name += '.session'
        
        if not new_name.endswith('.session'):
            new_name += '.session'
        
        old_path = os.path.join(UPLOAD_FOLDER, old_name)
        new_path = os.path.join(UPLOAD_FOLDER, new_name)
        
        if not os.path.exists(old_path):
            return jsonify({'error': 'Source file does not exist'}), 404
        
        if os.path.exists(new_path):
            return jsonify({'error': 'File with the new name already exists'}), 400
        
        os.rename(old_path, new_path)
        return jsonify({'success': f"File renamed to '{new_name}' successfully"}), 200
    except Exception as e:
        error_msg = f"Failed to rename file: {str(e)}"
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/delete/<path:filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'success': f"File '{filename}' successfully deleted"}), 200
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        error_msg = f"Failed to delete file: {str(e)}"
        print(f"Error: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': 'File not found'}), 404

def clear_screen():
    command = 'cls' if platform.system() == 'Windows' else 'clear'
    subprocess.call(command, shell=True)

def run_serveo():
    try:
        tunnel_process = subprocess.Popen(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-R", "80:localhost:5000", "serveo.net"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        for line in tunnel_process.stdout:
            decoded_line = line.decode()
            if "Forwarding" in decoded_line:
                clear_screen()
                panel_url = decoded_line.split("from")[1].strip()
                print(f"Panel available at: {panel_url}")
                break
    except Exception as e:
        print(f"Error starting Serveo tunnel: {e}")

async def run_web_and_tunnel():
    global flask_process, tunnel_process
    
    clear_screen()
    
    os.environ["FLASK_APP"] = "bot/utils/web.py"
    flask_process = subprocess.Popen(
        ["flask", "run", "--host", "0.0.0.0", "--port", "7777"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    tunnel_process = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-R", "80:localhost:7777", "serveo.net"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print("Starting web server and tunnel. Please wait...")
    while True:
        line = tunnel_process.stdout.readline().decode().strip()
        if "Forwarding" in line:
            print(f"Panel available at: {line.split()[-1]}")
            print("Press Ctrl+C to exit.")
            break
    while True:
        await asyncio.sleep(1)

async def stop_web_and_tunnel():
    global flask_process, tunnel_process
    if flask_process:
        flask_process.terminate()
        flask_process.wait()
    if tunnel_process:
        tunnel_process.terminate()
        tunnel_process.wait()
    print("Web server and tunnel stopped.")

if __name__ == '__main__':
    print(f"UPLOAD_FOLDER path: {UPLOAD_FOLDER}")
    print(f"UPLOAD_FOLDER absolute path: {os.path.abspath(UPLOAD_FOLDER)}")
    print(f"Current working directory: {os.getcwd()}")
    app.run(host='0.0.0.0', port=7777)

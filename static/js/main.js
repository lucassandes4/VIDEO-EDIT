/**
 * Video Editor - Frontend JavaScript
 * Gerencia upload de arquivos, drag and drop, e processamento
 */

// Estado da aplicação
const state = {
    sessionId: generateSessionId(),
    narration: null,
    media: [],
    subtitle: null,
    background: null,
    backgroundVolumeDb: -15
};

// Gera ID de sessão único
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Inicialização
document.addEventListener('DOMContentLoaded', () => {
    initDropZones();
    initFileInputs();
    initVolumeSlider();
    updateProcessButton();
});

// Inicializa as drop zones
function initDropZones() {
    const dropZones = document.querySelectorAll('.drop-zone');

    dropZones.forEach(zone => {
        zone.addEventListener('dragover', handleDragOver);
        zone.addEventListener('dragleave', handleDragLeave);
        zone.addEventListener('drop', handleDrop);
        zone.addEventListener('click', handleZoneClick);
    });
}

// Inicializa os inputs de arquivo
function initFileInputs() {
    document.getElementById('narration-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0], 'narration');
        }
    });

    document.getElementById('media-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadMediaFiles(e.target.files);
        }
    });

    document.getElementById('subtitle-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0], 'subtitle');
        }
    });

    document.getElementById('background-input').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0], 'background');
        }
    });
}

// Inicializa o controle de volume
function initVolumeSlider() {
    const slider = document.getElementById('volume-slider');

    slider.addEventListener('input', () => {
        const value = parseInt(slider.value);
        state.backgroundVolumeDb = value;
        document.getElementById('volume-value').textContent = `${value} dB`;

        // Atualiza botões de preset
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.classList.remove('active');
        });
    });
}

// Define o volume pelos presets
function setVolume(db) {
    state.backgroundVolumeDb = db;
    document.getElementById('volume-slider').value = db;
    document.getElementById('volume-value').textContent = `${db} dB`;

    // Atualiza botões de preset
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.remove('active');
        if ((db === -30 && btn.textContent === 'Baixo') ||
            (db === -15 && btn.textContent === 'Médio') ||
            (db === -6 && btn.textContent === 'Alto')) {
            btn.classList.add('active');
        }
    });
}

// Handlers de drag and drop
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('drag-over');

    const type = e.currentTarget.dataset.type;
    const files = e.dataTransfer.files;

    if (files.length > 0) {
        if (type === 'media') {
            uploadMediaFiles(files);
        } else {
            uploadFile(files[0], type);
        }
    }
}

function handleZoneClick(e) {
    // Evita clique duplo quando clica no botão
    if (e.target.tagName === 'BUTTON' || e.target.tagName === 'INPUT') {
        return;
    }

    const type = e.currentTarget.dataset.type;
    const inputId = `${type}-input`;
    document.getElementById(inputId).click();
}

// Upload de arquivo único
async function uploadFile(file, type) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', type);
    formData.append('session_id', state.sessionId);

    try {
        showToast(`Enviando ${file.name}...`, 'info');

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            // Atualiza estado
            state[type] = {
                path: result.path,
                filename: result.filename
            };

            // Atualiza UI
            updateFilePreview(type, result.filename);
            showToast(`${file.name} enviado com sucesso!`, 'success');

            // Mostra controle de volume se for background
            if (type === 'background') {
                document.getElementById('volume-control').style.display = 'block';
            }

            updateProcessButton();
        } else {
            showToast(result.error || 'Erro ao enviar arquivo', 'error');
        }
    } catch (error) {
        console.error('Erro no upload:', error);
        showToast('Erro ao enviar arquivo. Tente novamente.', 'error');
    }
}

// Upload de múltiplos arquivos de mídia
async function uploadMediaFiles(files) {
    for (const file of files) {
        await uploadMediaFile(file);
    }
}

async function uploadMediaFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', 'media');
    formData.append('session_id', state.sessionId);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            // Adiciona ao estado
            state.media.push({
                path: result.path,
                filename: result.filename,
                file: file
            });

            // Atualiza UI
            renderMediaList();
            updateProcessButton();
        } else {
            showToast(result.error || `Erro ao enviar ${file.name}`, 'error');
        }
    } catch (error) {
        console.error('Erro no upload de mídia:', error);
        showToast(`Erro ao enviar ${file.name}`, 'error');
    }
}

// Atualiza preview de arquivo único
function updateFilePreview(type, filename) {
    const dropzone = document.getElementById(`${type}-dropzone`);
    const preview = document.getElementById(`${type}-preview`);

    dropzone.classList.add('has-file');
    preview.style.display = 'flex';
    preview.querySelector('.filename').textContent = filename;
}

// Remove arquivo
function removeFile(type) {
    state[type] = null;

    const dropzone = document.getElementById(`${type}-dropzone`);
    const preview = document.getElementById(`${type}-preview`);

    dropzone.classList.remove('has-file');
    preview.style.display = 'none';

    // Esconde controle de volume se remover background
    if (type === 'background') {
        document.getElementById('volume-control').style.display = 'none';
    }

    // Limpa input
    document.getElementById(`${type}-input`).value = '';

    updateProcessButton();
}

// Renderiza lista de mídias
function renderMediaList() {
    const container = document.getElementById('media-list');
    container.innerHTML = '';

    state.media.forEach((media, index) => {
        const item = createMediaItem(media, index);
        container.appendChild(item);
    });

    // Inicializa drag and drop para reordenação
    initMediaDragSort();
}

// Cria item de mídia
function createMediaItem(media, index) {
    const item = document.createElement('div');
    item.className = 'media-item';
    item.dataset.index = index;
    item.draggable = true;

    const isVideo = /\.(mp4|avi|mov|mkv|webm)$/i.test(media.filename);

    let thumbnail;
    if (isVideo) {
        thumbnail = document.createElement('video');
        thumbnail.src = URL.createObjectURL(media.file);
        thumbnail.muted = true;
        thumbnail.addEventListener('loadeddata', () => {
            thumbnail.currentTime = 0;
        });
    } else {
        thumbnail = document.createElement('img');
        thumbnail.src = URL.createObjectURL(media.file);
        thumbnail.alt = media.filename;
    }

    const overlay = document.createElement('div');
    overlay.className = 'media-overlay';
    overlay.innerHTML = `
        <span class="media-order">${index + 1}</span>
        <span class="media-filename">${media.filename}</span>
    `;

    const removeBtn = document.createElement('button');
    removeBtn.className = 'media-remove';
    removeBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
    `;
    removeBtn.onclick = (e) => {
        e.stopPropagation();
        removeMedia(index);
    };

    item.appendChild(thumbnail);
    item.appendChild(overlay);
    item.appendChild(removeBtn);

    return item;
}

// Remove mídia da lista
function removeMedia(index) {
    state.media.splice(index, 1);
    renderMediaList();
    updateProcessButton();
}

// Drag and drop para reordenação de mídias
function initMediaDragSort() {
    const container = document.getElementById('media-list');
    let draggedItem = null;

    container.querySelectorAll('.media-item').forEach(item => {
        item.addEventListener('dragstart', (e) => {
            draggedItem = item;
            item.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
        });

        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            draggedItem = null;
        });

        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (draggedItem && draggedItem !== item) {
                const rect = item.getBoundingClientRect();
                const midX = rect.left + rect.width / 2;

                if (e.clientX < midX) {
                    container.insertBefore(draggedItem, item);
                } else {
                    container.insertBefore(draggedItem, item.nextSibling);
                }

                // Atualiza ordem no estado
                updateMediaOrder();
            }
        });
    });
}

// Atualiza ordem das mídias após reordenação
function updateMediaOrder() {
    const container = document.getElementById('media-list');
    const items = container.querySelectorAll('.media-item');
    const newOrder = [];

    items.forEach((item, newIndex) => {
        const oldIndex = parseInt(item.dataset.index);
        newOrder.push(state.media[oldIndex]);
        item.dataset.index = newIndex;
        item.querySelector('.media-order').textContent = newIndex + 1;
    });

    state.media = newOrder;
}

// Atualiza estado do botão de processamento
function updateProcessButton() {
    const btn = document.getElementById('process-btn');
    const canProcess = state.narration && state.media.length > 0;
    btn.disabled = !canProcess;
}

// Processa o vídeo
async function processVideo() {
    if (!state.narration || state.media.length === 0) {
        showToast('Adicione o áudio de narração e pelo menos uma mídia', 'warning');
        return;
    }

    // Mostra seção de progresso
    document.querySelectorAll('.upload-section, .process-section').forEach(el => {
        el.style.display = 'none';
    });
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('result-section').style.display = 'none';

    try {
        const data = {
            narration_path: state.narration.path,
            media_files: state.media.map(m => m.path),
            subtitle_path: state.subtitle?.path || null,
            background_path: state.background?.path || null,
            background_volume_db: state.backgroundVolumeDb
        };

        updateProgressStatus('Enviando dados para processamento...');

        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showResult(result);
        } else {
            throw new Error(result.error || 'Erro no processamento');
        }
    } catch (error) {
        console.error('Erro no processamento:', error);
        showToast(error.message || 'Erro ao processar vídeo', 'error');

        // Volta para a view de upload
        document.getElementById('progress-section').style.display = 'none';
        document.querySelectorAll('.upload-section, .process-section').forEach(el => {
            el.style.display = 'block';
        });
    }
}

// Atualiza status do progresso
function updateProgressStatus(message) {
    document.getElementById('progress-status').textContent = message;
}

// Mostra resultado
function showResult(result) {
    document.getElementById('progress-section').style.display = 'none';
    document.getElementById('result-section').style.display = 'block';

    // Configura vídeo
    const video = document.getElementById('result-video');
    video.src = `/api/preview/${result.output_filename}`;

    // Configura botão de download
    const downloadBtn = document.getElementById('download-btn');
    downloadBtn.href = result.download_url;
    downloadBtn.download = result.output_filename;
}

// Reseta o editor
function resetEditor() {
    // Reseta estado
    state.sessionId = generateSessionId();
    state.narration = null;
    state.media = [];
    state.subtitle = null;
    state.background = null;
    state.backgroundVolumeDb = -15;

    // Reseta UI
    document.getElementById('result-section').style.display = 'none';
    document.querySelectorAll('.upload-section, .process-section').forEach(el => {
        el.style.display = 'block';
    });

    // Limpa previews
    ['narration', 'subtitle', 'background'].forEach(type => {
        const dropzone = document.getElementById(`${type}-dropzone`);
        const preview = document.getElementById(`${type}-preview`);
        if (dropzone) dropzone.classList.remove('has-file');
        if (preview) preview.style.display = 'none';
    });

    // Limpa lista de mídias
    document.getElementById('media-list').innerHTML = '';

    // Esconde controle de volume
    document.getElementById('volume-control').style.display = 'none';

    // Reseta slider de volume
    document.getElementById('volume-slider').value = -15;
    document.getElementById('volume-value').textContent = '-15 dB';
    setVolume(-15);

    // Limpa inputs
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.value = '';
    });

    updateProcessButton();
}

// Toast notifications
function showToast(message, type = 'info') {
    // Remove toast existente
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

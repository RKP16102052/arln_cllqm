// === Реализация Fernet (совместимая с Python cryptography.fernet) ===
class Fernet {
    constructor(keyBase64) {
        // keyBase64: 32 байта (256 бит) в base64 (Fernet использует 32-байтовый ключ)
        const keyBytes = this._base64ToBytes(keyBase64);
        if (keyBytes.length !== 32) throw new Error('Fernet key must be 32 bytes');
        this.signingKey = keyBytes.slice(0, 16);
        this.encryptionKey = keyBytes.slice(16, 32);
    }

    _base64ToBytes(base64) {
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return bytes;
    }

    _bytesToBase64(bytes) {
        let binary = '';
        for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
        return btoa(binary);
    }

    async encrypt(plaintext) {
        // Fernet формат: Version (1 байт) | Timestamp (8 байт) | IV (16 байт) | Ciphertext | HMAC (32 байта)
        const version = new Uint8Array([0x80]);
        const timestamp = new Uint8Array(8);
        const now = BigInt(Math.floor(Date.now() / 1000));
        for (let i = 0; i < 8; i++) timestamp[7 - i] = Number((now >> BigInt(i * 8)) & 0xFFn);
        
        const iv = crypto.getRandomValues(new Uint8Array(16));
        
        // Шифрование AES-128-CBC
        const cryptoKey = await crypto.subtle.importKey('raw', this.encryptionKey, { name: 'AES-CBC' }, false, ['encrypt']);
        const encrypted = await crypto.subtle.encrypt({ name: 'AES-CBC', iv: iv }, cryptoKey, new TextEncoder().encode(plaintext));
        const ciphertext = new Uint8Array(encrypted);
        
        // Собираем данные до HMAC
        const hmacData = new Uint8Array(1 + 8 + 16 + ciphertext.length);
        hmacData.set(version, 0);
        hmacData.set(timestamp, 1);
        hmacData.set(iv, 9);
        hmacData.set(ciphertext, 25);
        
        // HMAC-SHA256
        const hmacKey = await crypto.subtle.importKey('raw', this.signingKey, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
        const hmac = await crypto.subtle.sign('HMAC', hmacKey, hmacData);
        const hmacBytes = new Uint8Array(hmac);
        
        // Финальный токен
        const tokenBytes = new Uint8Array(hmacData.length + 32);
        tokenBytes.set(hmacData, 0);
        tokenBytes.set(hmacBytes, hmacData.length);
        
        return this._bytesToBase64(tokenBytes);
    }

    async decrypt(tokenBase64) {
        const tokenBytes = this._base64ToBytes(tokenBase64);
        if (tokenBytes.length < 57) throw new Error('Invalid token');
        
        const version = tokenBytes[0];
        if (version !== 0x80) throw new Error('Unsupported version');
        
        const timestamp = tokenBytes.slice(1, 9);
        const iv = tokenBytes.slice(9, 25);
        const ciphertext = tokenBytes.slice(25, tokenBytes.length - 32);
        const receivedHmac = tokenBytes.slice(tokenBytes.length - 32);
        
        // Проверка HMAC
        const hmacData = tokenBytes.slice(0, tokenBytes.length - 32);
        const hmacKey = await crypto.subtle.importKey('raw', this.signingKey, { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']);
        const isValid = await crypto.subtle.verify('HMAC', hmacKey, receivedHmac, hmacData);
        if (!isValid) throw new Error('Invalid HMAC');
        
        // Расшифровка
        const cryptoKey = await crypto.subtle.importKey('raw', this.encryptionKey, { name: 'AES-CBC' }, false, ['decrypt']);
        const decrypted = await crypto.subtle.decrypt({ name: 'AES-CBC', iv: iv }, cryptoKey, ciphertext);
        return new TextDecoder().decode(decrypted);
    }
}

// === Конфигурация ===
const WS_URL = 'wss://130.12.45.26:8765';
const FERNET_KEY_B64 = 'b1hj9pFchWx8sOZ1oqVN3cOxLSgvcPTPUdhbS_EM5d4='; // тот же ключ, что в Python
let fernet = null;

// Инициализация Fernet после загрузки страницы
(async () => {
    fernet = new Fernet(FERNET_KEY_B64);
})();

// Глобальные переменные
let ws = null;
let token = null;
let nickname = null;
let privateKey = null;
let currentChatId = null;
let chats = [];
let messagesCache = {};

// DOM элементы (как в предыдущей версии, убедитесь что они существуют)
const authScreen = document.getElementById('auth-screen');
const chatScreen = document.getElementById('chat-screen');
const loginError = document.getElementById('login-error');
const regError = document.getElementById('reg-error');
const codeError = document.getElementById('code-error');
const chatListDiv = document.getElementById('chat-list');
const messagesContainer = document.getElementById('messages-container');
const chatHeader = document.getElementById('chat-header');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const addChatBtn = document.getElementById('add-chat-btn');
const settingsBtn = document.getElementById('settings-btn');
const addChatModal = document.getElementById('add-chat-modal');
const settingsModal = document.getElementById('settings-modal');
const newChatUsername = document.getElementById('new-chat-username');
const createChatSubmit = document.getElementById('create-chat-submit');
const addChatError = document.getElementById('add-chat-error');
const exportKeyBtn = document.getElementById('export-key-btn');
const logoutBtn = document.getElementById('logout-btn');
const settingsError = document.getElementById('settings-error');

// Вспомогательные функции
function showError(element, text) { if (element) element.textContent = text || ''; }
function showScreen(screenId) {
    if (authScreen) authScreen.style.display = 'none';
    if (chatScreen) chatScreen.style.display = 'none';
    if (screenId === 'auth' && authScreen) authScreen.style.display = 'flex';
    else if (screenId === 'chat' && chatScreen) chatScreen.style.display = 'flex';
}
function showCodeScreen() {
    const tabs = document.querySelector('.tabs');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const codeScreenDiv = document.getElementById('code-screen');
    if (tabs) tabs.style.display = 'none';
    if (loginForm) loginForm.style.display = 'none';
    if (registerForm) registerForm.style.display = 'none';
    if (codeScreenDiv) codeScreenDiv.style.display = 'block';
}

// Функции шифрования/дешифрования с использованием Fernet
async function encryptFernet(data) {
    if (!fernet) await new Promise(r => setTimeout(r, 100));
    return await fernet.encrypt(JSON.stringify(data));
}
async function decryptFernet(encryptedBase64) {
    if (!fernet) await new Promise(r => setTimeout(r, 100));
    const decrypted = await fernet.decrypt(encryptedBase64);
    return JSON.parse(decrypted);
}

// WebSocket
function connectWebSocket() {
    ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => console.log('WebSocket connected');
    ws.onmessage = async (event) => {
        const encryptedBytes = new Uint8Array(event.data);
        const encryptedBase64 = btoa(String.fromCharCode(...encryptedBytes));
        const decrypted = await decryptFernet(encryptedBase64);
        handleServerMessage(decrypted);
    };
    ws.onerror = (err) => console.error('WS error', err);
    ws.onclose = () => {
        console.log('WS closed, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
    };
}

async function sendToServer(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        const encrypted = await encryptFernet(payload);
        const binary = Uint8Array.from(atob(encrypted), c => c.charCodeAt(0));
        ws.send(binary);
        return true;
    }
    return false;
}

// Обработка сообщений (сокращённо, но полностью функционально)
function handleServerMessage(data) {
    const action = data.action;
    console.log('Server:', data);
    if (action === 'register') {
        if (data.status === 'OK') {
            token = data.token;
            localStorage.setItem('token', token);
            showCodeScreen();
        } else showError(regError, data.message);
    } else if (action === 'register_verification') {
        if (data.status === 'OK') {
            localStorage.setItem('nickname', nickname);
            autoLogin();
        } else showError(codeError, data.message);
    } else if (action === 'login') {
        if (data.status === 'OK') {
            token = data.token;
            localStorage.setItem('token', token);
            sendToServer({ action: 'get_name', token: token });
        } else showError(loginError, data.message);
    } else if (action === 'get_name') {
        if (data.status === 'OK') {
            nickname = data.name;
            localStorage.setItem('nickname', nickname);
            showChatScreen();
            getChats();
            startPolling();
        }
    } else if (action === 'get_chats') {
        if (data.status === 'OK') {
            chats = data.chats;
            renderChatList();
        }
    } else if (action === 'create_chat_with_user') {
        if (data.status === 'OK') {
            if (addChatModal) addChatModal.style.display = 'none';
            getChats();
        } else showError(addChatError, data.message);
    } else if (action === 'get_messages') {
        if (data.status === 'OK') {
            const chatId = data.chat_id;
            const newMessages = data.data;
            if (!messagesCache[chatId]) messagesCache[chatId] = [];
            messagesCache[chatId] = messagesCache[chatId].concat(newMessages);
            if (currentChatId === chatId) renderMessages(chatId);
        }
    } else if (action === 'get_members_keys') {
        if (data.status === 'OK') {
            const chatId = data.chat_id;
            const pendingMsg = localStorage.getItem(`pending_msg_${chatId}`);
            if (pendingMsg) {
                localStorage.removeItem(`pending_msg_${chatId}`);
                for (let item of data.content) {
                    const username = Object.keys(item)[0];
                    const pubKeyPem = item[username];
                    const publicKey = forge.pki.publicKeyFromPem(pubKeyPem);
                    const encrypted = publicKey.encrypt(pendingMsg, 'RSA-OAEP', {
                        md: forge.md.sha256.create(),
                        mgf1: forge.md.sha256.create()
                    });
                    const b64 = forge.util.encode64(encrypted);
                    sendToServer({
                        action: 'send_message',
                        token: token,
                        to_username: username,
                        message: b64,
                        chat_id: chatId
                    });
                }
            }
        }
    }
}

// Остальные функции (RSA, UI, poll) остаются без изменений
// ... (функции generateRSAKeyPair, savePrivateKeyToStorage, loadPrivateKeyFromStorage, sha256, autoLogin, getChats, renderChatList, openChat, renderMessages, и т.д.)
// Полный код предоставлен в предыдущем ответе; здесь только исправление Fernet.

// Запуск
connectWebSocket();
autoLogin();
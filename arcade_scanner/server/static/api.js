// api.js - Extracted from engine.js

// --- GLOBAL AUTH INTERCEPTOR ---
const originalFetch = window.fetch;
window.fetch = async function (...args) {
    const response = await originalFetch(...args);
    if (response.status === 401) {
        // Redirect to login page.
        // Return a promise that never resolves so no downstream .json()/.text()
        // call can accidentally consume the already-drained response body.
        window.location.href = '/static/login.html';
        return new Promise(() => {});
    }
    return response;
};


// Tự động phát hiện môi trường
const getApiUrl = () => {
    const hostname = window.location.hostname;
    
    // Nếu đang chạy trên máy mình (localhost hoặc 127.0.0.1)
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return "http://127.0.0.1:5000";
    }
    
    // Nếu chạy trên server thật (buser.com, render, heroku...)
    // window.location.origin sẽ lấy: https://domain-cua-ban.com
    return window.location.origin;
};

const API_URL = getApiUrl();
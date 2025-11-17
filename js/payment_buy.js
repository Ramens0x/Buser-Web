$(document).ready(function () {

    // --- Hàm lấy Token ---
    function getAuthToken() {
        const loginDataString = localStorage.getItem('buser_login_data');
        if (!loginDataString) return null;
        try {
            const loginData = JSON.parse(loginDataString);
            return loginData.token;
        } catch (e) { return null; }
    }

    // --- Hàm định dạng số (Cần thiết) ---
    function numberFormat(number = '0', decimalPlaces = 0) {
        let numberStr = parseFloat(number).toFixed(decimalPlaces);
        let parts = numberStr.split('.');
        let integerPart = parts[0];
        let decimalPart = parts.length > 1 ? '.' + parts[1] : '';
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        return integerPart + decimalPart;
    }

    const token = getAuthToken();
    const orderDataString = localStorage.getItem('current_order');

    if (!token) {
        window.location.href = "login.html";
        return;
    }
    if (!orderDataString) {
        alert("Không tìm thấy thông tin đơn hàng.");
        window.location.href = "index.html";
        return;
    }

    const order = JSON.parse(orderDataString);

    // --- 1. Cập nhật Khung 1: Thông tin thanh toán (Của Admin) ---
    const info = order.payment_info;
    if (info) {
        $('#order-id').text(escapeHTML(order.id));
        $('#payment-bank').text(info.bank);
        $('#payment-account-number').text(escapeHTML(info.account_number));
        $('#payment-account-name').text(escapeHTML(info.account_name));
        $('#payment-amount').text(numberFormat(info.amount, 0) + ' VNĐ');
        $('#payment-content').text(escapeHTML(info.content));

        const qrData = encodeURIComponent(order.qr_data_string);
        const qrImgSrc = `${API_URL}/api/generate-qr?data=${qrData}`;
        $('#qr-image').attr('src', qrImgSrc);
    }

    // --- 2. [MỚI] Cập nhật Khung 2: Thông tin nhận (Của User) ---
    $('#confirm-coin-type').text(order.coin.toUpperCase());
    $('#confirm-coin-amount').text(numberFormat(order.amount_coin, 8));

    // Gọi API để lấy chi tiết ví user đã chọn
    $.ajax({
        url: `${API_URL}/api/user/wallets?coin_type=${order.coin}`,
        type: 'GET',
        beforeSend: function (xhr) {
            xhr.setRequestHeader('Authorization', 'Bearer ' + token);
        },
        success: function (response) {
            const selectedWallet = response.wallets.find(w => w.id === order.user_wallet_id);

            if (selectedWallet) {
                $('#confirmation-wallet-details').remove();

                let detailsHtml = `
                    <li id="confirmation-wallet-details">
                        <strong>Địa chỉ ví:</strong> <span style="color: #333;">${escapeHTML(selectedWallet.address)}</span>
                    </li>`;

                if (order.coin === 'bustabit') {
                    detailsHtml += `
                        <li><strong>Tag/Memo:</strong> <span style="color: #333;">${escapeHTML(selectedWallet.tag) || 'Không có'}</span></li>
                        <li><strong>Họ tên:</strong> <span style="color: #333;">${escapeHTML(selectedWallet.name)}</span></li>
                        <li><strong>SĐT:</strong> <span style="color: #333;">${escapeHTML(selectedWallet.phone)}</span></li>
                    `;
                }
                $('#confirm-coin-amount').closest('li').after(detailsHtml);
            }
        },
        error: function (xhr) {
            console.error("Lỗi khi tải chi tiết ví.");
        }
    });
});
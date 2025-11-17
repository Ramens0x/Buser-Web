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

    // --- 1. Cập nhật Khung 1: Thông tin gửi coin (Của Admin) ---
    const info = order.payment_info;
    if (info) {
        $('#order-id').text(escapeHTML(order.id));
        $('#sell-amount').text(numberFormat(order.amount_coin, 8));
        $('#sell-coin-type').text(order.coin.toUpperCase());

        $('#admin-wallet-network').text(info.network);
        $('#admin-wallet-address').text(escapeHTML(info.wallet_address));
        // [CẬP NHẬT] Ẩn/hiện ô Memo (Vì Bustabit không cần)
        if (info.memo) {
            $('#admin-wallet-memo-li').show();
            $('#admin-wallet-memo').text(escapeHTML(info.memo));
        } else {
            $('#admin-wallet-memo-li').hide();
        }
    }

    // --- 2. [MỚI] Cập nhật Khung 2: Thông tin nhận VNĐ (Của User) ---
    $('#receive-amount-vnd').text(numberFormat(order.amount_vnd, 0));
    $.ajax({
        url: `${API_URL}/api/user/banks`,
        type: 'GET',
        beforeSend: function (xhr) {
            xhr.setRequestHeader('Authorization', 'Bearer ' + token);
        },
        success: function (response) {
            const selectedBank = response.banks.find(b => b.id === order.user_bank_id);

            if (selectedBank) {
                $('#user-bank-name').text(escapeHTML(selectedBank.bank_name));
                $('#user-bank-account').text(escapeHTML(selectedBank.account_number));
                $('#user-account-name').text(escapeHTML(selectedBank.account_name));
            }
        },
        error: function (xhr) {
            console.error("Lỗi khi tải chi tiết ngân hàng.");
        }
    });
});
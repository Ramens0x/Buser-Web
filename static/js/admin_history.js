$(document).ready(function () {

    // --- Hàm lấy Token (Cần thiết cho API) ---
    function getAuthToken() {
        const loginDataString = localStorage.getItem('buser_login_data');
        if (!loginDataString) return null;
        try {
            const loginData = JSON.parse(loginDataString);
            return loginData.token;
        } catch (e) { return null; }
    }

    const token = getAuthToken();
    if (!token) {
        window.location.href = "login.html";
        return;
    }

    // --- Tải dữ liệu giao dịch ĐÃ HOÀN THÀNH ---
    function loadTransactionHistory() {
        $.ajax({
            url: `${API_URL}/api/admin/transactions/history`,
            type: 'GET',
            success: function (response) {
                if (response.success) {
                    renderHistoryTable(response.transactions);
                }
            },
            error: function (xhr) {
                alert("Lỗi tải lịch sử: " + xhr.responseJSON.message);
                window.location.href = "index.html"; // Đá về trang chủ nếu không phải Admin
            }
        });
    }

    // --- Hiển thị dữ liệu lên bảng ---
    function renderHistoryTable(transactions) {
        const tableBody = $('#history-table-body');
        tableBody.empty(); // Xóa dòng "Đang tải..."

        if (transactions.length === 0) {
            tableBody.append('<tr><td colspan="7" class="text-center">Không có giao dịch nào đã hoàn thành.</td></tr>');
            return;
        }

        transactions.forEach(tx => {
            // [MỚI] Xác định link dựa trên loại đơn (Mua hay Bán)
            // API trả về tx.mode là "Mua" hoặc "Bán" (Tiếng Việt) hoặc "buy"/"sell"
            let linkPage = 'checkout_payment_buy.html'; // Mặc định là trang Mua
            if (tx.mode === 'Bán' || tx.mode === 'sell') {
                linkPage = 'checkout_payment_sell.html'; // Chuyển sang trang Bán
            }

            // Tạo đường dẫn có ID (target="_blank" để mở tab mới)
            const idLink = `<a href="${linkPage}?id=${escapeHTML(tx.id)}" target="_blank" style="font-weight: bold; text-decoration: underline;">${escapeHTML(tx.id)}</a>`;

            const row = `
                <tr>
                    <td>${idLink}</td> <td>${escapeHTML(tx.created_at)}</td>
                    <td>${escapeHTML(tx.username)}</td>
                    <td>${escapeHTML(tx.mode)}</td>
                    <td>${escapeHTML(tx.coin)}</td>
                    <td>${numberFormat(tx.amount_coin, 8)}</td>
                    <td>${numberFormat(tx.amount_vnd, 0)} VNĐ</td>
                </tr>`;
            tableBody.append(row);
        });
    }

    // --- Chạy lần đầu ---
    loadTransactionHistory();
});
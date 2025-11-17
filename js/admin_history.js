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

    // --- Hàm định dạng số ---
    function numberFormat(number = '0', decimalPlaces = 0) {
        let numberStr = parseFloat(number).toFixed(decimalPlaces);
        let parts = numberStr.split('.');
        let integerPart = parts[0];
        let decimalPart = parts.length > 1 ? '.' + parts[1] : '';
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        return integerPart + decimalPart;
    }

    // --- Tải dữ liệu giao dịch ĐÃ HOÀN THÀNH ---
    function loadTransactionHistory() {
        $.ajax({
            url: `${API_URL}/api/admin/transactions/history`, // GỌI API MỚI
            type: 'GET',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            },
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
            const row = `
                <tr>
                    <td><strong>${escapeHTML(tx.id)}</strong></td>
                    <td>${tx.created_at}</td>
                    <td>${escapeHTML(tx.username)}</td>
                    <td>${tx.mode}</td>
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
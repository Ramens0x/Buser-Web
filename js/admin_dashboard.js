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

    // --- Tải dữ liệu giao dịch ---
    function loadTransactions() {
        $.ajax({
            url: `${API_URL}/api/admin/transactions`,
            type: 'GET',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            },
            success: function (response) {
                if (response.success) {
                    renderTables(response.transactions);

                    if (response.stats) {
                        $('#stat-vnd-in').text(numberFormat(response.stats.total_vnd_in, 0) + ' ₫');
                        $('#stat-vnd-out').text(numberFormat(response.stats.total_vnd_out, 0) + ' ₫');
                        $('#stat-bustabit').text(numberFormat(response.stats.total_bustabit_volume, 8));
                        $('#stat-usdt').text(numberFormat(response.stats.total_usdt_volume, 2));
                    }
                }
            },
            error: function (xhr) {
                alert("Lỗi tải giao dịch: " + xhr.responseJSON.message);
                window.location.href = "index.html"; // Đá về trang chủ nếu không phải Admin
            }
        });
    }

    // --- Hiển thị dữ liệu lên bảng ---
    function renderTables(transactions) {
        const buyTable = $('#buy-orders-table');
        const sellTable = $('#sell-orders-table');
        buyTable.empty();
        sellTable.empty();

        let buyCount = 0;
        let sellCount = 0;

        transactions.forEach(order => {
            if (order.mode === 'buy') {
                // Đơn Mua: Admin cần gửi Coin
                buyCount++;
                const row = `
                    <tr id="order-${order.id}">
                        <td><strong>${order.id}</strong></td>
                        <td>${escapeHTML(order.username)}</td>
                        <td>${numberFormat(order.amount_coin, 8)} ${order.coin.toUpperCase()}</td>
                        <td>
                            (Tạm thời: Sẽ hiển thị chi tiết ví ở đây)
                            <br>ID Ví: ${escapeHTML(order.user_wallet_id)}
                        </td>
                        <td>
                            <button class="btn btn-sm btn-primary btn-complete" data-id="${order.id}">
                                <i class="fa fa-check"></i> Đã Gửi Coin
                            </button>
                        </td>
                    </tr>`;
                buyTable.append(row);

            } else {
                // Đơn Bán: Admin cần gửi VNĐ
                sellCount++;
                const row = `
                    <tr id="order-${order.id}">
                        <td><strong>${order.id}</strong></td>
                        <td>${escapeHTML(order.username)}</td>
                        <td>${numberFormat(order.amount_vnd, 0)} VNĐ</td>
                        <td>
                            (Tạm thời: Sẽ hiển thị chi tiết Bank ở đây)
                            <br>ID Bank: ${escapeHTML(order.user_bank_id)}
                        </td>
                        <td>
                            <button class="btn btn-sm btn-warning btn-complete" data-id="${order.id}">
                                <i class="fa fa-check"></i> Đã Chuyển VNĐ
                            </button>
                        </td>
                    </tr>`;
                sellTable.append(row);
            }
        });

        // Cập nhật thống kê
        $('#stat-buy-pending').text(buyCount);
        $('#stat-sell-pending').text(sellCount);

        if (buyCount === 0) buyTable.append('<tr><td colspan="5" class="text-center">Không có đơn MUA nào đang chờ.</td></tr>');
        if (sellCount === 0) sellTable.append('<tr><td colspan="5" class="text-center">Không có đơn BÁN nào đang chờ.</td></tr>');
    }

    // --- Xử lý nút "Hoàn tất" ---
    // (Dùng .on() vì các nút này được tạo động)
    $(document).on('click', '.btn-complete', function () {
        const orderId = $(this).data('id');
        if (!confirm(`Bạn có chắc chắn muốn hoàn tất đơn hàng ${orderId} không?`)) {
            return;
        }

        $.ajax({
            url: `${API_URL}/api/admin/transactions/complete`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ order_id: orderId }),
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            },
            success: function (response) {
                if (response.success) {
                    alert(response.message);
                    // Xóa hàng đó khỏi bảng
                    $(`#order-${orderId}`).fadeOut(500, function () {
                        $(this).remove();
                        // Tải lại để cập nhật số đếm
                        loadTransactions();
                    });
                }
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

    // --- Chạy lần đầu ---
    loadTransactions();
});
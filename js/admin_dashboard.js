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

    // --- Xử lý nút "Hủy Đơn" (Admin) ---
    $(document).on('click', '.btn-cancel-admin', function () {
        const orderId = $(this).data('id');
        if (!confirm(`ADMIN: Bạn có chắc chắn muốn HỦY đơn hàng ${orderId} không?`)) {
            return;
        }
        $.ajax({
            url: `${API_URL}/api/admin/cancel-order`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ order_id: orderId }),
            beforeSend: function (xhr) {
                xhr.setRequestHeader('Authorization', 'Bearer ' + token);
            },
            success: function (response) {
                alert(response.message);
                $(`#order-${orderId}`).fadeOut(500, function () {
                    $(this).remove();
                    loadTransactions();
                });
            },
            error: function (xhr) {
                alert("Lỗi: " + xhr.responseJSON.message);
            }
        });
    });

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
            // Nút hành động chung (Gửi Coin / Chuyển Tiền + Hủy)
            let actionBtns = '';
            if (order.mode === 'buy') {
                actionBtns = `<button class="btn btn-sm btn-primary btn-complete" data-id="${order.id}"><i class="fa fa-check"></i> Đã Gửi Coin</button>`;
            } else {
                actionBtns = `<button class="btn btn-sm btn-warning btn-complete" data-id="${order.id}"><i class="fa fa-check"></i> Đã Chuyển Tiền</button>`;
            }
            // Thêm nút hủy
            actionBtns += `<br><button class="btn btn-sm btn-danger btn-cancel-admin" data-id="${order.id}" style="margin-top:5px;"><i class="fa fa-times"></i> Hủy đơn</button>`;

            const row = `
                <tr id="order-${order.id}">
                    <td><a href="${order.mode === 'buy' ? 'checkout_payment_buy.html' : 'checkout_payment_sell.html'}?id=${order.id}" target="_blank"><strong>${order.id}</strong></a></td>
                    <td>${escapeHTML(order.username)}</td>
                    <td>${numberFormat(order.mode === 'buy' ? order.amount_coin : order.amount_vnd, order.mode === 'buy' ? 8 : 0)} ${order.mode === 'buy' ? order.coin.toUpperCase() : 'VNĐ'}</td>
                    <td>${order.coin.toUpperCase()}</td>
                    <td>${order.detail_info}</td> 
                    <td>${actionBtns}</td>
                </tr>`;

            if (order.mode === 'buy') { buyCount++; buyTable.append(row); }
            else { sellCount++; sellTable.append(row); }
        });


        $('#stat-buy-pending').text(buyCount);
        $('#stat-sell-pending').text(sellCount);
        if (buyCount === 0) buyTable.append('<tr><td colspan="6" class="text-center">Không có đơn MUA nào đang chờ.</td></tr>');
        if (sellCount === 0) sellTable.append('<tr><td colspan="6" class="text-center">Không có đơn BÁN nào đang chờ.</td></tr>');
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
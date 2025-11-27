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

    // --- Xử lý nút "Hủy Đơn" (Admin) ---
    $(document).on('click', '.btn-cancel-admin', function () {
        const btn = $(this); // [MỚI] Lưu lại nút đang bấm
        const orderId = btn.data('id'); // Sửa $(this) thành btn

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

                // [SỬA ĐOẠN NÀY] Xóa dòng chứa nút bấm (Chính xác 100%)
                btn.closest('tr').fadeOut(500, function () {
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
                        // VNĐ
                        $('#stat-vnd-in').text(numberFormat(response.stats.total_vnd_in, 0) + ' ₫');
                        $('#stat-vnd-out').text(numberFormat(response.stats.total_vnd_out, 0) + ' ₫');
                        $('#stat-vnd-in-month').text(numberFormat(response.stats.total_vnd_in_month, 0) + ' ₫');
                        $('#stat-vnd-out-month').text(numberFormat(response.stats.total_vnd_out_month, 0) + ' ₫');
                        
                        $('#stat-bustabit').text(numberFormat(response.stats.total_bustabit_volume, 8));
                        $('#stat-ether').text(numberFormat(response.stats.total_ether_volume, 8)); 
                        $('#stat-usdt').text(numberFormat(response.stats.total_usdt_volume, 2));
                        $('#stat-bnb').text(numberFormat(response.stats.total_bnb_volume, 4));     
                        $('#stat-sol').text(numberFormat(response.stats.total_sol_volume, 4));     
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

        const binMap = {
            'Vietcombank (VCB)': '970436',
            'VietinBank (ICB)': '970415',
            'BIDV': '970418',
            'Agribank': '970405',
            'Á Châu (ACB)': '970416',
            'MBBank (MB)': '970422',
            'Techcombank (TCB)': '970407',
            'Sacombank (STB)': '970403',
            'VPBank': '970432',
            'TPBank': '970423',
            'HDBank': '970437'
        };

        transactions.forEach(order => {
            let actionBtns = '';
            if (order.mode === 'buy') {
                actionBtns = `<button class="btn btn-sm btn-primary btn-complete" data-id="${order.id}"><i class="fa fa-check"></i> Đã Gửi Coin</button>`;
            } else {
                actionBtns = `<button class="btn btn-sm btn-warning btn-complete" data-id="${order.id}"><i class="fa fa-check"></i> Đã Chuyển Tiền</button>`;
            }
            actionBtns += `<br><button class="btn btn-sm btn-danger btn-cancel-admin" data-id="${order.id}" style="margin-top:5px;"><i class="fa fa-times"></i> Hủy đơn</button>`;

            let billLink = (order.bill_image && order.bill_image !== 'null') ? 
                `<br><a href="${API_URL}/api/admin/bill/${order.bill_image}" target="_blank" class="btn btn-xs btn-info" style="margin-top:5px;"><i class="fa fa-picture-o"></i> Xem Bill</a>` : 
                `<br><small style="color:#999;">Chưa có bill</small>`;

            if (order.mode === 'buy') {
                // Bảng MUA: 6 cột
                const row = `
                <tr id="order-${order.id}">
                    <td><a href="checkout_payment_buy.html?id=${order.id}" target="_blank"><strong>${order.id}</strong></a></td>
                    <td>${escapeHTML(order.username)}</td>
                    <td>${numberFormat(order.amount_coin, 8)} ${order.coin.toUpperCase()}</td>
                    <td>${order.coin.toUpperCase()}</td>
                    <td>${order.detail_info} ${billLink}</td> 
                    <td>${actionBtns}</td>
                </tr>`;
                buyTable.append(row);
                buyCount++;
            } else {
                // Bảng BÁN: 5 cột + QR Code + Copy Content
                let qrBtn = '';
                const copyBtn = `<button class="btn btn-xs btn-default" onclick="navigator.clipboard.writeText('${order.sell_content}');alert('Đã copy nội dung!')"><i class="fa fa-copy"></i> Copy ND</button>`;
                
                if (order.user_bank_raw) {
                    // 1. Tìm mã BIN dựa trên tên ngân hàng
                    let targetBin = '';
                    let bankNameRaw = order.user_bank_raw.bankName; // Lấy tên ngân hàng từ dữ liệu raw
                    
                    // Tra cứu trong danh sách
                    if (binMap[bankNameRaw]) {
                        targetBin = binMap[bankNameRaw];
                    } else {
                        // Nếu không tìm thấy key chính xác, thử tìm theo chuỗi (fallback)
                        for (const [name, code] of Object.entries(binMap)) {
                            if (bankNameRaw.includes(name)) { targetBin = code; break; }
                        }
                    }

                    // 2. Nếu có BIN, tạo link QR VietQR
                    if (targetBin) {
                        const qrUrl = `https://img.vietqr.io/image/${targetBin}-${order.user_bank_raw.accountNo}-compact.jpg?amount=${order.user_bank_raw.amount}&addInfo=${encodeURIComponent(order.user_bank_raw.addInfo)}&accountName=${encodeURIComponent(order.user_bank_raw.accountName)}`;
                        qrBtn = `<a href="${qrUrl}" target="_blank" class="btn btn-xs btn-success" style="margin-top:5px;"><i class="fa fa-qrcode"></i> Quét QR Trả Tiền</a>`;
                    } else {
                        qrBtn = `<br><small style="color:red;">(Không tìm thấy mã BIN)</small>`;
                    }
                }

                const row = `
                <tr id="order-${order.id}">
                    <td><a href="checkout_payment_sell.html?id=${order.id}" target="_blank"><strong>${order.id}</strong></a></td>
                    <td>${escapeHTML(order.username)}</td>
                    <td>${numberFormat(order.amount_vnd, 0)} VNĐ</td>
                    <td>
                        ${order.detail_info} ${billLink}
                        <hr style="margin: 5px 0;">
                        <div style="background:#f9f9f9; padding:5px; border-radius:4px;">
                            <small style="color:#d9534f; font-weight:bold;">ND: ${order.sell_content}</small>
                            <br>${copyBtn} ${qrBtn}
                        </div>
                    </td> 
                    <td>${actionBtns}</td>
                </tr>`;
                sellTable.append(row);
                sellCount++;
            }
        });

        $('#stat-buy-pending').text(buyCount);
        $('#stat-sell-pending').text(sellCount);
        if (buyCount === 0) buyTable.append('<tr><td colspan="6" class="text-center">Không có đơn MUA nào đang chờ.</td></tr>');
        if (sellCount === 0) sellTable.append('<tr><td colspan="5" class="text-center">Không có đơn BÁN nào đang chờ.</td></tr>');
    }

    // --- Xử lý nút "Hoàn tất" ---
    $(document).on('click', '.btn-complete', function () {
        const btn = $(this); // [MỚI] Lưu lại nút đang bấm
        const orderId = btn.data('id');

        if (!confirm(`Bạn có chắc chắn muốn hoàn tất đơn hàng ${orderId} không?`)) {
            return;
        }

        $.ajax({
            // ... (các phần url, type giữ nguyên) ...
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
                    btn.closest('tr').fadeOut(500, function () {
                        $(this).remove();

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